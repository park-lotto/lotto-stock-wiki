import subject_stage_pool as ST
"""Measured subject selection, with explicit audio/video evidence and dense tracking.

Coordinates are source pixels; the server owns placement and quality policy.
No channel names, inferred identities, downloads or implicit provider changes.
"""
import copy
from contextlib import contextmanager, ExitStack
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import volcano_run as R
import runtime_metrics as M

ALGORITHM_VERSION = 3


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _http_failure_code(code):
    """Keep HTTP exception/failed-receipt status codes in the string envelope."""
    return str(code) if type(code) is int and 400 <= code <= 599 else code


def _box(value, width, height):
    return (isinstance(value, list) and len(value) == 4 and all(_number(v) for v in value)
            and value[0] >= 0 and value[1] >= 0 and value[2] > 0 and value[3] > 0
            and value[0] + value[2] <= width + 1e-6 and value[1] + value[3] <= height + 1e-6)


def _union(boxes):
    x = min(b[0] for b in boxes); y = min(b[1] for b in boxes)
    right = max(b[0] + b[2] for b in boxes); bottom = max(b[1] + b[3] for b in boxes)
    return [x, y, right - x, bottom - y]


def _policy(item):
    p = item['policy']
    t = p['tracking']
    if (not _number(p['sample_interval']) or p['sample_interval'] <= 0
            or not _number(p['scene_threshold']) or not 0 < p['scene_threshold'] < 1
            or not _number(t['max_error_px']) or t['max_error_px'] <= 0
            or type(t['min_points']) is not int or t['min_points'] < 3
            or not _number(t['min_inlier_fraction']) or not 0 < t['min_inlier_fraction'] <= 1
            or p['refinement_rounds'] not in (0, 1)):
        raise R.StepError('피사체 측정 정책이 잘못되었습니다. 서버의 새 계획을 받으세요.')
    return p


def _video_timing(cut):
    """Validate the server's derived redub grid before any receipt is reused."""
    if 'video_timing' not in cut:
        return None
    start, duration, fps = (cut.get(k) for k in ('start', 'duration', 'fps'))
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (start, duration, fps)):
        raise R.StepError('재더빙 영상의 시간 계획이 현재 컷과 다릅니다.')
    try:
        start, duration, fps = float(start), float(duration), float(fps)
    except (ValueError, OverflowError) as exc:
        raise R.StepError('재더빙 영상의 시간 계획이 현재 컷과 다릅니다.') from exc
    if (cut.get('kind') != 'video' or cut.get('seek_mode') != 'trim'
            or not all(math.isfinite(v) for v in (start, duration, fps))
            or start < 0 or duration <= 0 or fps <= 0
            or not math.isfinite(start+duration) or not math.isfinite(duration*fps)):
        raise R.StepError('재더빙 영상의 시간 계획이 현재 컷과 다릅니다.')
    begin, end = float(f'{start:.3f}'), float(f'{start+duration:.3f}')
    frames = (end-begin)*fps
    if not math.isfinite(frames):
        raise R.StepError('재더빙 영상의 시간 계획이 현재 컷과 다릅니다.')
    count = round(frames)
    expected = (f'trim=start={begin:.3f}:end={end:.3f},setpts=PTS-STARTPTS,'
                f'fps={fps:g},tpad=stop_mode=clone:stop=1,'
                f'trim=end_frame={count},setpts=PTS-STARTPTS')
    if (count < 1 or count != round(duration*fps) or cut['video_timing'] != expected
            or abs(begin-start) > 1e-9 or abs(end-start-duration) > 1e-9):
        raise R.StepError('재더빙 영상의 시간 계획이 현재 컷과 다릅니다.')
    return expected


def _source_timeline(cut, directory, source_sha=None):
    """Byte/tool-bound local timing evidence, independent of semantic receipts."""
    if cut.get('kind') == 'image':
        return None
    executable = (cut.get('tracking_probe_argv') or ['ffprobe'])[0]
    tool = Path(shutil.which(executable) or executable).resolve()
    stat = tool.stat()
    recipe = dict(version=1, source_identity=source_sha or _sha(cut['src']),
                  tool=[str(tool), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns])
    cache_key = hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()
    receipt = directory.parent/'source-timelines'/f'{cache_key}.json'
    receipt.parent.mkdir(parents=True,exist_ok=True)
    def interval(probe):
        try:
            stream = probe['streams'][0]
            raw = (probe['format']['start_time'], stream['start_time'], stream['duration'])
            if any(isinstance(v, bool) or not isinstance(v, (str, int, float)) for v in raw): return None
            origin, begin, length = (Decimal(str(v)) for v in raw)
            end = begin+length
            if not all(math.isfinite(v) for v in (origin, begin, length, end)) or length <= 0: return None
            return dict(origin=float(origin), start=float(begin-origin), end=float(end-origin),
                        source_start=float(begin), source_end=float(end))
        except (KeyError, IndexError, TypeError, ValueError, OverflowError, InvalidOperation): return None
    with R.review_receipt_lock(str(receipt)):
        try: saved = json.loads(receipt.read_text(encoding='utf-8'))
        except (OSError, ValueError): saved = None
        timing = interval(saved.get('probe')) if isinstance(saved, dict) and saved.get('recipe') == recipe else None
        if timing is None:
            result = R.run_argv([executable, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                'stream=start_time,duration:format=start_time', '-of', 'json', cut['src']], capture=True)
            if result.returncode: raise R.StepError('원본 화면의 공통 시간축을 측정하지 못했습니다.')
            try: probe = json.loads(result.stdout)
            except ValueError: probe = None
            streams = probe.get('streams') or [] if isinstance(probe,dict) else []
            if streams and streams[0].get('duration') in (None,'N/A'):
                # Stream duration is optional in Matroska. Audio/container duration
                # is not video EOF: observe actual video packets locally instead.
                begin = end = None
                with subprocess.Popen([str(tool),'-v','error','-select_streams','v:0','-show_packets',
                        '-show_entries','packet=pts_time,duration_time','-of','compact=p=0:nk=0',cut['src']],
                        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8') as process:
                    for line in process.stdout:
                        packet = dict(part.split('=',1) for part in line.strip().split('|') if '=' in part)
                        try: at, length = Decimal(packet['pts_time']), Decimal(packet['duration_time'])
                        except (KeyError, InvalidOperation, TypeError): continue
                        if not at.is_finite() or not length.is_finite() or length <= 0: continue
                        begin = at if begin is None else min(begin,at)
                        end = at+length if end is None else max(end,at+length)
                    process.stdout.close()
                    if process.wait(): raise R.StepError('원본 영상 패킷의 실제 끝을 측정하지 못했습니다.')
                if begin is not None and end is not None:
                    stream = streams[0]
                    if stream.get('start_time') in (None,'N/A'): stream['start_time'] = str(begin)
                    try: length = end-Decimal(stream['start_time'])
                    except InvalidOperation: length = Decimal('NaN')
                    if length.is_finite() and length > 0: stream['duration'] = str(length)
            timing = interval(probe)
            if timing is None: raise R.StepError('원본 화면의 시작·끝 시각 또는 공통 PTS 기준이 없습니다.')
            R._photo_write_state(str(receipt),dict(recipe=recipe,probe=probe))
    start = cut.get('start')
    if not _number(start) or start < max(0.,timing['start']) or start >= timing['end']:
        raise R.StepError(f"{cut.get('card','')}: 요청 시작 시각에는 원본 화면이 없습니다. "
            f"영상·음성 공통 시간축의 실제 화면 구간은 {max(0.,timing['start']):.6f}~{timing['end']:.6f}초입니다. "
            "원본 구간을 바로잡으세요. 완료된 검수·음성은 보존합니다.")
    return timing


def _check_source_pts(pts, cut, timing):
    if timing is None: return
    # fps chooses real neighboring pictures, including a picture just beyond
    # the requested end; only actual stream availability is a hard PTS bound.
    # Existing showinfo receipts store pts_time printed with FFmpeg's %g
    # (six significant digits), so compare against that same declared precision.
    # This is display quantization, not permission to substitute another frame.
    end = max(timing['source_end'], float(f"{timing['source_end']:.6g}"))
    begin = min(timing['source_start'], float(f"{timing['source_start']:.6g}"))
    if any(p is not None and (not _number(p) or p < begin or p >= end) for p in pts):
        raise R.StepError('저장된 source_pts가 실제 원본 화면 구간과 다릅니다. 유료 검수를 반복하지 않습니다.')


def _legacy_frame_recipe(cut, policy, source_sha):
    # Only extraction inputs belong here. A new review answer/context does not
    # change these pixels, their source PTS or their measured scene boundaries.
    tools = []
    executables = (() if cut.get('kind')=='image' else
                   (cut['frame_argv'][0], (cut.get('tracking_probe_argv') or ['ffprobe'])[0]))
    for executable in executables:
        path = Path(shutil.which(executable) or executable).resolve()
        try:
            stat = path.stat()
        except OSError:
            # Let the normal executor report/install a missing executable.
            return None
        tools.append([str(path),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns])
    return dict(version=1,source_identity=source_sha,tools=tools,
                cut={k:cut.get(k) for k in ('src','kind','start','duration','fps','seek_mode','video_timing')},
                scene_threshold=policy['scene_threshold'])


def _frame_recipe(cut, policy, source_sha):
    from subject_decoder_identity import binary_identity
    legacy = _legacy_frame_recipe(cut, policy, source_sha)
    if legacy is None:return None
    try:tools = [binary_identity(Path(row[0])) for row in legacy['tools']]
    except OSError as error:
        raise R.StepError('디코더 원본 바이트를 확인하지 못했습니다. 기존 프레임·검수 증거를 보존합니다.') from error
    timing=dict(legacy['cut'])
    if 'frame_clock' in cut:timing['frame_clock']=cut['frame_clock']
    return dict(legacy,version=2,tools=tools,cut=timing,
                extraction_algorithm='legacy-seek-fps-v1' if 'frame_clock' not in cut else cut['frame_clock'])


def _frame_recipe_matches(previous,current,cut,policy,directory):
    import sys
    from subject_decoder_identity import compatible
    return compatible(sys.modules[__name__],previous,current,cut,policy,directory)


def _record_frame_decoder(saved,current,cut,policy,directory,source_digest=None):
    import sys
    from subject_decoder_identity import record_verified
    record_verified(sys.modules[__name__],saved,current,cut,policy,directory,source_digest=source_digest)


_FRAME_STORAGE_LOCK = threading.Lock()
_FRAME_STORAGE_RESERVED = {}


@contextmanager
def _frame_storage_reservation(cut, directory, count):
    """Reserve conservative local PNG space without deleting existing evidence.

    Budget 16-bit RGBA scanlines plus 1% encoding overhead and 4KiB per file;
    compression savings are deliberately not assumed. This is a local estimate,
    not a provider limit, and other processes can still consume disk space.
    """
    probe = R.run_argv([(cut.get('tracking_probe_argv') or ['ffprobe'])[0],
        '-v','error','-select_streams','v:0','-show_entries','stream=width,height',
        '-of','json',cut['src']], capture=True)
    try:
        stream = json.loads(probe.stdout)['streams'][0]
        width, height = stream['width'], stream['height']
        if probe.returncode or type(width) is not int or type(height) is not int or min(width,height) <= 0:
            raise ValueError('invalid dimensions')
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise R.StepError('프레임 저장 공간을 계산할 원본 해상도를 확인하지 못했습니다. 기존 증거를 보존합니다.') from error
    raw = (width * 8 + 1) * height
    required = count * (raw + raw // 100 + 4096)
    device = directory.stat().st_dev
    with _FRAME_STORAGE_LOCK:
        free = shutil.disk_usage(directory).free
        reserved = _FRAME_STORAGE_RESERVED.get(device, 0)
        if free - reserved < required:
            raise R.StepError('프레임 측정 저장 공간이 부족합니다. 압축 전 기준 예상 %d바이트, '
                '다른 진행 컷 예약 제외 여유 %d바이트. 기존 검수·음성·프레임은 보존했습니다. '
                '다른 작업 파일을 옮기거나 공간을 확보한 뒤 같은 단계로 재개하세요.' % (required,max(0,free-reserved)))
        _FRAME_STORAGE_RESERVED[device] = reserved + required
    try:
        yield
    finally:
        with _FRAME_STORAGE_LOCK:
            remaining = _FRAME_STORAGE_RESERVED[device] - required
            if remaining: _FRAME_STORAGE_RESERVED[device] = remaining
            else: _FRAME_STORAGE_RESERVED.pop(device, None)


def _frame_transaction_files(directory):
    return sorted(directory.glob('frame_*.png')) + [p for p in
        (directory/'video-timing.json', directory/'frame-evidence.json') if p.exists()]


def _recover_frame_transaction(directory):
    """Restore original paths before reading receipts after an interrupted cutover.

    The journal precedes every move. Recovery itself is repeatable after another
    interruption: restored originals have their recorded digest. Neither old
    evidence nor the interrupted new files are deleted.
    """
    journal = directory/'frame-transaction.json'
    if not journal.exists(): return
    try:
        state = json.loads(journal.read_text(encoding='utf-8'))
        name = state['transaction']
        valid_name = isinstance(name, str) and name.startswith('.frame-evidence-') and Path(name).name == name
        originals, incoming = state['originals'], state['incoming']
        names = set(originals) | set(incoming)
        if (not valid_name or not isinstance(originals, dict) or not isinstance(incoming, list)
                or any(not re.fullmatch(r'frame_\d+\.png|frame-evidence\.json|video-timing\.json', v) for v in names)):
            raise ValueError('invalid frame transaction')
        transaction = directory.parent/name
        backup = transaction/'original'
        interrupted = transaction/'interrupted'; interrupted.mkdir(exist_ok=True)
        # Restore pixels/timing first and the old manifest last.
        for filename in sorted(names, key=lambda v: (v == 'frame-evidence.json', v)):
            target, old = directory/filename, backup/filename
            if filename in originals:
                if old.exists():
                    if _sha(old) != originals[filename]: raise ValueError('backup digest mismatch')
                    if target.exists(): os.replace(target, interrupted/filename)
                    os.replace(old, target)
                elif not target.exists() or _sha(target) != originals[filename]:
                    raise ValueError('original evidence missing or changed: ' + filename)
            elif target.exists():
                os.replace(target, interrupted/filename)
        os.replace(journal, transaction/'recovered.json')
    except Exception as error:
        raise R.StepError('프레임 교체 복구를 완료하지 못했습니다. 기존 증거와 새 사본을 보존했습니다: '
                          + str(journal) + ' (' + str(error) + ')') from error


def _publish_frame_transaction(directory, transaction, stage):
    """Publish validated local pixels; never move paid receipts or review caches."""
    backup = transaction/'original'; backup.mkdir()
    originals = _frame_transaction_files(directory)
    incoming = _frame_transaction_files(stage)
    # ffmpeg has closed its outputs; flush their bytes before the durable intent.
    for path in incoming:
        with path.open('r+b') as stream: os.fsync(stream.fileno())
    journal = directory/'frame-transaction.json'
    R._photo_write_state(str(journal), dict(transaction=transaction.name,
        originals={p.name:_sha(p) for p in originals}, incoming=[p.name for p in incoming]))
    try:
        # Remove the old manifest first so no partial set appears complete.
        for path in sorted(originals, key=lambda p: (p.name != 'frame-evidence.json', p.name)):
            os.replace(path, backup/path.name)
        for path in incoming:  # helper lists the new manifest last
            os.replace(path, directory/path.name)
        os.replace(journal, transaction/'committed.json')
    except Exception:
        _recover_frame_transaction(directory)
        raise


@M.span('subject_extraction', publish=True)
def _frames(cut, directory, policy, *, wanted_indices=None, source_digest=None, timeline=None, before_decode=None):
    """Reuse only a complete, byte-checked measurement across review handoffs."""
    _video_timing(cut)
    digest = source_digest or _sha
    source_sha = digest(cut['src'])
    timeline = timeline if timeline is not None else _source_timeline(cut, directory, source_sha)
    recipe = _frame_recipe(cut,policy,source_sha)
    count = 1 if cut.get('kind')=='image' else round(float(cut['duration'])*float(cut['fps']))
    if wanted_indices is not None:
        if (cut.get('kind')!='video' or not isinstance(wanted_indices,list) or not wanted_indices
                or any(type(i) is not int or not 0<=i<count for i in wanted_indices)
                or wanted_indices!=sorted(set(wanted_indices))):
            raise R.StepError('글자 검수 프레임 번호가 원래 영상 격자와 다릅니다.')
        if recipe is not None:recipe=dict(recipe,frame_indices=wanted_indices)
    image_count=count if wanted_indices is None else len(wanted_indices)
    if cut.get('kind') == 'image':
        return _decode_frames(cut,directory,policy,wanted_indices=wanted_indices,timeline=timeline,
                              before_decode=before_decode)
    manifest = directory/'frame-evidence.json'
    with R.review_receipt_lock(str(manifest)):
        _recover_frame_transaction(directory)
        previous = None
        try:
            saved = json.loads(manifest.read_text(encoding='utf-8'))
            paths = [directory/f'frame_{i:06d}.png' for i in range(image_count)]
            previous = saved
            pts, cuts, digests = saved['pts'], saved['cuts'], saved['sha256']
            if (recipe is not None and _frame_recipe_matches(saved['recipe'],recipe,cut,policy,directory) and count>0
                    and all(isinstance(v,list) for v in (digests,pts,cuts)) and len(digests)==image_count
                    and len(pts)==count and all(p is None or _number(p) for p in pts)
                    and cuts==sorted(set(cuts)) and all(type(i) is int and 0<i<count for i in cuts)
                    and sorted(directory.glob('frame_*.png'))==paths
                    and all(_sha(p)==digest for p,digest in zip(paths,digests))):
                # Timing evidence controls the independently prepared review
                # proxy too; a missing/changed receipt must be remeasured.
                timing = directory/'video-timing.json'
                if (cut.get('video_timing') is None or
                        (timing.is_file() and _sha(timing)==saved['timing_sha256'])):
                    if digest(cut['src']) != source_sha:
                        raise R.StepError('피사체 프레임 재개 중 원본 바이트가 바뀌었습니다.')
                    _check_source_pts(pts, cut, timeline)
                    _record_frame_decoder(saved,recipe,cut,policy,directory,source_digest=digest)
                    M.event('subject_extraction', 'reused')
                    return paths,cuts,pts
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            pass
        if before_decode: before_decode()
        # Space is checked before creating a staging folder or moving evidence.
        # Keep the request-key basename for video-timing and paid receipt binding.
        with _frame_storage_reservation(cut, directory, image_count):
            transaction = Path(tempfile.mkdtemp(prefix='.frame-evidence-', dir=directory.parent))
            stage = transaction/directory.name; stage.mkdir()
            try:
                paths,cuts,pts = _decode_frames(cut,stage,policy,wanted_indices=wanted_indices,timeline=timeline)
                _check_source_pts(pts, cut, timeline)
                if digest(cut['src']) != source_sha:
                    raise R.StepError('피사체 프레임 측정 중 원본 바이트가 바뀌었습니다.')
                saved = dict(recipe=recipe,cuts=cuts,pts=pts,sha256=[_sha(p) for p in paths],
                             scene_algorithm='native-grid-v3')
                if cut.get('video_timing') is not None:
                    saved['timing_sha256'] = _sha(stage/'video-timing.json')
                # Repair bytes without changing an existing question's sample grid.
                # A same-recipe manifest binds pending/paid reviews to these exact
                # pixels and scene indices, even if the detector has improved.
                if isinstance(previous, dict) and _frame_recipe_matches(previous.get('recipe'),recipe,cut,policy,directory):
                    if (previous.get('sha256') != saved['sha256'] or previous.get('pts') != pts
                            or not isinstance(previous.get('cuts'), list)
                            or previous['cuts'] != sorted(set(previous['cuts']))
                            or any(type(i) is not int or not 0 < i < count for i in previous['cuts'])
                            or previous.get('timing_sha256') != saved.get('timing_sha256')):
                        raise R.StepError('기존 검수 프레임의 원래 바이트·시간축을 복원하지 못했습니다. '
                                          '이전 증거를 보존하고 유료 검수 재요청 전에 멈춥니다.')
                    saved = previous
                    cuts = saved['cuts']
                    shutil.copyfile(manifest, stage/'frame-evidence.json')
                else:
                    R._photo_write_state(str(stage/'frame-evidence.json'),saved)
                _publish_frame_transaction(directory, transaction, stage)
            except Exception as error:
                error.frame_evidence_staging = str(transaction)
                if hasattr(error, 'add_note'):
                    error.add_note('기존 증거와 새 측정 사본 보존: ' + str(transaction))
                raise
        return [directory/p.name for p in paths],cuts,pts


def _frames_for_selection(cut, directory, item, policy, *, source_digest=None, timeline=None,
                          before_decode=None):
    """Share only pristine extraction receipts; keep all semantic review evidence in place.

    An existing legacy semantic file keeps the original directory, including
    incomplete or unknown paid reviews. A new shared extraction records its
    exact recipe pointer in the semantic directory before decoding so a later
    review resume uses the same pixels. The source timeline is always prepared
    using the semantic directory before selecting a pixel cache.
    """
    digest = source_digest or _sha
    source_sha = digest(cut['src'])
    if timeline is None and '_timeline_locks' in item:
        with item['_timeline_lock_guard']:
            timeline_lock = item['_timeline_locks'].setdefault(source_sha, threading.Lock())
        with timeline_lock:
            timeline = _source_timeline(cut, directory, source_sha)
    elif timeline is None:
        timeline = _source_timeline(cut, directory, source_sha)
    recipe = (_frame_recipe(cut, policy, source_sha)
              if _visual_subject(cut) and cut.get('frame_argv') else None)
    target = directory
    pointer = directory/'frame-cache-ref.json'
    pointer_lock = directory/'frame-cache-ref.json.lock'
    linked_review = False
    key = None
    if recipe is not None:
        key = hashlib.sha256(json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        # This nonwaiting cross-process lock protects the choice of legacy vs
        # shared pixels as well as the atomic pointer publication. A competing
        # execution fails closed instead of seeing a temporary .photo-state
        # file and selecting the wrong directory for a paid question.
        with R.review_receipt_lock(str(pointer)):
            if pointer.exists():
                try:
                    saved = json.loads(pointer.read_text(encoding='utf-8'))
                except (OSError, ValueError) as error:
                    raise R.StepError('공유 프레임 경로 기록을 읽지 못했습니다. 기존 검수 증거를 보존합니다.') from error
                if (not isinstance(saved, dict) or set(saved) != {'version', 'recipe_sha256'}
                        or type(saved['version']) is not int or saved['version'] != 1
                        or not isinstance(saved.get('recipe_sha256'),str)
                        or not re.fullmatch('[0-9a-f]{64}',saved['recipe_sha256'])):
                    raise R.StepError('공유 프레임 경로가 현재 원본·시간·추출 조건과 다릅니다. 기존 검수 증거를 보존합니다.')
                target = Path(item['out_dir'])/'.frame-cache'/saved['recipe_sha256']
                if saved['recipe_sha256'] != key:
                    try:previous=json.loads((target/'frame-evidence.json').read_text(encoding='utf-8'))['recipe']
                    except (OSError,ValueError,KeyError,TypeError) as error:
                        raise R.StepError('기존 공유 프레임 정체성 증거를 읽지 못했습니다. 유료 검수를 재전송하지 않습니다.') from error
                    from subject_decoder_identity import recipe_sha
                    if recipe_sha(previous)==saved['recipe_sha256'] and not _frame_recipe_matches(previous,recipe,cut,policy,target):
                        import subject_decoder_recovery as DR, sys
                        DR.recover(sys.modules[__name__],cut,policy,target,recipe,timeline,digest)
                    import subject_sampled_recovery as SR
                    if (recipe_sha(previous)!=saved['recipe_sha256']
                            or (not _frame_recipe_matches(previous,recipe,cut,policy,target)
                                and not SR.candidate(previous,recipe))):
                        raise R.StepError('과거 디코더 바이트를 확인할 수 없습니다. 기존 검수·프레임을 보존합니다.')
                    key=saved['recipe_sha256']
                linked_review = any(p not in (pointer, pointer_lock) and p.name not in ('frame-clock-choice.json','frame-clock-choice.json.lock','clock-execution.lock') for p in directory.iterdir())
                if not (target/'frame-evidence.json').exists() and linked_review:
                    raise R.StepError('검수 기록에 연결된 공유 프레임 영수증이 없습니다. 유료 검수를 재전송하지 않습니다.')
            elif not any(p != pointer_lock and p.name not in ('frame-clock-choice.json','frame-clock-choice.json.lock','clock-execution.lock') for p in directory.iterdir()):
                target = Path(item['out_dir'])/'.frame-cache'/key
                R._photo_write_state(str(pointer), {'version': 1, 'recipe_sha256': key})
        if target != directory:
            target.mkdir(parents=True, exist_ok=True)
    # Capture this before _frames opens its nonwaiting OS lock, which creates a
    # .lock file. A previously published or partial shared pixel set must not
    # be rebuilt merely because this semantic question has no review receipt.
    shared_had_evidence = (target != directory and any(
        p.name != 'frame-evidence.json.lock' for p in target.iterdir()))
    other_linked_review = False
    if target != directory and not shared_had_evidence:
        # The entire shared folder may have been moved after a paid review.
        # Its semantic pointer and review receipt survive in the original
        # question folder, so a new question cannot silently regenerate it.
        try:
            for sibling in Path(item['out_dir']).iterdir():
                if sibling == directory or sibling.is_symlink() or not sibling.is_dir():
                    continue
                other_pointer = sibling/'frame-cache-ref.json'
                if not other_pointer.is_file():
                    continue
                linked = json.loads(other_pointer.read_text(encoding='utf-8'))
                if (isinstance(linked, dict) and linked.get('recipe_sha256') == key
                        and any(p not in (other_pointer, sibling/'frame-cache-ref.json.lock')
                                and p.name not in ('frame-clock-choice.json','frame-clock-choice.json.lock','clock-execution.lock')
                                for p in sibling.iterdir())):
                    other_linked_review = True
                    break
        except (OSError, ValueError) as error:
            raise R.StepError('기존 공유 프레임의 검수 연결 상태를 확인하지 못했습니다. 재디코딩하지 않습니다.') from error
    def read():
        def before_extraction():
            if linked_review or shared_had_evidence or other_linked_review:
                raise R.StepError('검수 기록에 연결된 프레임을 원래 바이트로 확인하지 못했습니다. '
                                  '기존 유료 검수·프레임을 보존하고 재전송하지 않습니다.')
            if before_decode:
                before_decode()
        from subject_frame_stream import sampled_frames
        import sys
        import subject_decoder_recovery as DR
        manifest=target/'frame-evidence.json'
        if recipe is not None and manifest.exists():
            previous=json.loads(manifest.read_text(encoding='utf-8')).get('recipe')
            if not _frame_recipe_matches(previous,recipe,cut,policy,target):
                if not DR.recover(sys.modules[__name__],cut,policy,target,recipe,timeline,digest):
                    import subject_sampled_recovery as SR
                    result=SR.frames(sys.modules[__name__],cut,target,policy,digest,timeline)
                    item['_local_recovery_only']=True
                    return result
        result=sampled_frames(sys.modules[__name__], cut, target, policy, source_digest=digest,
                              timeline=timeline, before_decode=before_extraction)
        if recipe is not None and DR.valid(target,recipe):item['_local_recovery_only']=True
        return result
    if target == directory or '_frame_locks' not in item:
        return read()
    with item['_frame_lock_guard']:
        lock = item['_frame_locks'].setdefault(key, threading.Lock())
    with lock:
        return read()



def _frame_select_expression(indices):
    """Exact membership with logarithmic parser depth, not a left-deep sum.

    Every requested index remains an eq term; only associative parentheses
    change. No sample removal, rounding, source replacement or timing change.
    """
    terms = [f'eq(n,{index})' for index in indices]
    if not terms:
        raise ValueError('frame selection is empty')
    while len(terms) > 1:
        terms = [f'({terms[i]}+{terms[i+1]})' if i+1 < len(terms) else terms[i]
                 for i in range(0,len(terms),2)]
    return terms[0]


def _decode_frames(cut, directory, policy, *, wanted_indices=None, timeline=None, before_decode=None, _command_only=False):
    """Decode the same seek/fps phase as the declared video review/render cut.

    showinfo before fps retains decoded source timestamps. A unique checksum
    associates an output frame with that real timestamp. Repeated identical
    source pictures are honestly marked ambiguous, never assigned an invented PTS.
    """
    from PIL import Image
    declared_timing = _video_timing(cut)
    start, fps = float(cut['start']), float(cut['fps'])
    if not math.isfinite(start) or start < 0 or not math.isfinite(fps) or fps <= 0:
        raise R.StepError('피사체 측정의 시작 시각 또는 fps가 잘못되었습니다.')
    if cut.get('kind') == 'image':
        # An RGB PNG source is used in place; anything else is normalized once
        # into a content-addressed PNG (no fixed-name copy of the picture).
        with Image.open(cut['src']) as image:
            if image.format == 'PNG' and image.mode == 'RGB':
                return [Path(cut['src'])], [], [None]
            if before_decode: before_decode()
            target = Path(R._frozen_png(image.convert('RGB'), directory))
        return [target], [], [None]
    duration = float(cut['duration'])
    n = round(duration * fps)
    if not math.isfinite(duration) or duration <= 0 or n < 1:
        raise R.StepError('피사체 측정의 길이가 잘못되었습니다.')
    ffmpeg = cut['frame_argv'][0]
    # Input seek normally subtracts a time-base-rounded offset. Keep original
    # decoded PTS for evidence, then apply that same offset only to the fps path.
    probe_argv = cut.get('tracking_probe_argv') or ['ffprobe']
    timeline = timeline if timeline is not None else _source_timeline(cut, directory)
    origin = timeline['origin']
    trim = cut.get('seek_mode') == 'trim'
    if cut.get('seek_mode') not in (None, 'seek', 'trim'):
        raise R.StepError('피사체 측정의 seek_mode를 알 수 없습니다.')
    timing = (f'setpts=PTS-round({origin:.12g}/TB),trim=start={start:.12g}:end={start+duration:.12g},setpts=PTS-STARTPTS'
              if trim else f'setpts=PTS-round({start + origin:.12g}/TB)')
    grid = f'{timing},fps={fps:.12g}'
    clock = cut.get('frame_clock')
    if clock is not None:
        import subject_frame_clock as FC
        if trim or declared_timing is not None:
            raise R.StepError('source frame clock cannot override an existing timing recipe')
        try: grid = FC.grid(cut,timeline)
        except ValueError as exc: raise R.StepError(str(exc)) from exc
    if declared_timing is not None:
        # Container duration can belong to a longer audio stream. Inspect real
        # video packets around this cut; one held frame cannot conceal true EOF.
        packets = R.run_argv([probe_argv[0], '-v', 'error', '-select_streams', 'v:0',
            '-read_intervals', f'{start+origin:.12g}%{start+origin+duration+1/fps:.12g}',
            '-show_entries', 'packet=pts_time,duration_time', '-of', 'json', cut['src']], capture=True)
        if packets.returncode:
            raise R.StepError('원본 영상의 실제 끝을 측정하지 못했습니다.')
        ends = []
        for packet in json.loads(packets.stdout).get('packets', []):
            try:
                pts, length = float(packet['pts_time']), float(packet.get('duration_time') or 0)
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(pts) and math.isfinite(length) and math.isfinite(pts+length) and length >= 0:
                ends.append(pts + length)
        # Picks use source-relative milliseconds. Quantize the measured end on
        # that same grid, after removing the source timestamp origin.
        if not ends or round(max(ends)-origin, 3) < start+duration-1e-6:
            raise R.StepError('원본 영상의 실제 끝이 요청 구간보다 부족하거나 측정되지 않았습니다.')
        # Observe the pre-hold count so an already complete proxy/question keeps
        # its original command and receipt. The held frame retains real PTS.
        grid = (f'setpts=PTS-round({origin:.12g}/TB),'
                + declared_timing.replace(',tpad=', ',showinfo@focus_fps,tpad='))
    selected=(",select='"+_frame_select_expression(wanted_indices)+"'" if wanted_indices is not None else '')
    # Score original frames, then retain every event before fps can discard or
    # duplicate its frame. The native timestamps below use the same trimmed
    # timeline and exact time bases as fps, including its nearest rounding.
    grid = grid.replace(',fps=', ',metadata@focus_native=mode=print:key=lavfi.scene_score,'
                        'showinfo@focus_native,fps=', 1)
    graph = (f"[0:v]showinfo@focus_source,select='gte(scene,0)',{grid},"
             'metadata@focus_scene=mode=print:key=lavfi.scene_score,'
             f'showinfo@focus_cut,showinfo@focus_all{selected}[frames]')
    args = [ffmpeg, '-y', '-hide_banner', '-nostats', '-loglevel', 'info',
            '-filter_complex_threads', '1', '-copyts']
    if clock is not None:
        args = args[:-1] if args[-1] == '-copyts' else args
        args += FC.input_options(cut,timeline)
    elif not trim:
        args += ['-ss', str(start), '-t', str(duration)]
    args += ['-i', cut['src'], '-filter_complex', graph,
            '-map', '[frames]', '-frames:v', str(n), '-fps_mode', 'passthrough',
            '-start_number', '0', str(directory / 'frame_%06d.png')]
    if _command_only:
        return args
    p = R.run_argv(args, capture=True)
    def failed(message, evidence=None):
        # Keep the full decoder log locally; outbound diagnostics contain only
        # the bounded numeric mismatch, never source paths or FFmpeg arguments.
        (directory/'frame-error.log').write_text(p.stderr or '',encoding='utf-8')
        if evidence is not None:
            R._photo_write_state(str(directory/'frame-error.json'),evidence)
            message += ' '+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))
        raise R.StepError(message)
    if p.returncode:
        failed('피사체 프레임 측정 실패: ' + (p.stderr or '')[-1200:])
    return _decoded_frame_evidence(cut,directory,policy,p.stderr,sorted(directory.glob('frame_*.png')),wanted_indices)


def _decoded_frame_evidence(cut,directory,policy,stderr,paths,wanted_indices=None):
    declared_timing=_video_timing(cut)
    fps=float(cut['fps']);n=round(float(cut['duration'])*fps)
    def failed(message,evidence=None):
        (directory/'frame-error.log').write_text(stderr or '',encoding='utf-8')
        if evidence is not None:
            R._photo_write_state(str(directory/'frame-error.json'),evidence)
            message += ' '+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))
        raise R.StepError(message)
    records = {k: [] for k in ('source', 'fps', 'all', 'cut')}
    scores = {}; score_frame = None
    native_scores = {}; native_frame = None
    native_ticks = {}; time_bases = {}; first_output_tick = None
    # FFmpeg's log records are identified by filter prefixes, not newline
    # boundaries. Progress/other logging can concatenate complete records.
    for line in re.split(r'(?=\[(?:showinfo@focus_|metadata@focus_(?:scene|native)))', stderr or ''):
        tag = re.search(r'showinfo@focus_(source|fps|all|cut|native)', line)
        if tag and tag[1] in ('native', 'all'):
            base = re.search(r'config in time_base:\s*(\d+)/(\d+)', line)
            if base: time_bases[tag[1]] = Fraction(int(base[1]), int(base[2]))
            tick = re.search(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)', line)
            if tick and tag[1] == 'native': native_ticks[int(tick[1])] = int(tick[2])
            if tick and tag[1] == 'all' and first_output_tick is None:
                first_output_tick = int(tick[2])
        values = re.search(r'\bn:\s*(\d+).*?pts_time:([-+\deE.]+).*?checksum:([A-Fa-f0-9]+)', line)
        if tag and values and tag[1] in records:
            records[tag[1]].append((int(values[1]), float(values[2]), values[3]))
        if 'metadata@focus_scene' in line:
            frame = re.search(r'\bframe:\s*(\d+)', line)
            score = re.search(r'lavfi.scene_score=([-+\deE.]+)', line)
            if frame: score_frame = int(frame[1])
            if score and score_frame is not None: scores[score_frame] = float(score[1])
        if 'metadata@focus_native' in line:
            frame = re.search(r'\bframe:\s*(\d+)', line)
            score = re.search(r'lavfi.scene_score=([-+\deE.]+)', line)
            if frame: native_frame = int(frame[1])
            if score and native_frame is not None: native_scores[native_frame] = float(score[1])
    actual = records['all'][:n]
    expected_images=n if wanted_indices is None else len(wanted_indices)
    if len(paths) != expected_images or len(actual) != n or [v[0] for v in actual] != list(range(n)):
        failed(f'피사체 프레임 수가 요청과 다릅니다: 요청 {n}, 파일 {len(paths)}, 실측 {len(actual)}',dict(
            expected_images=expected_images,record_counts={k:len(v) for k,v in records.items()},
            first_wrong_indices=[[i,v[0]] for i,v in enumerate(actual) if i!=v[0]][:8],
            missing_indices=sorted(set(range(n))-{v[0] for v in actual})[:8]))
    first_pts = actual[0][1]
    if any(abs(v[1] - first_pts - i / fps) > 1e-4 for i, v in enumerate(actual)):
        failed('피사체 측정 프레임의 fps 위상이 요청과 다릅니다.',dict(
            fps=fps,first_pts=first_pts,first_wrong_pts=[[i,v[1],first_pts+i/fps] for i,v in enumerate(actual)
                if abs(v[1]-first_pts-i/fps)>1e-4][:8]))
    if (records['cut'][:n] != actual or any(i not in scores or not math.isfinite(scores[i]) for i in range(n))):
        mismatches=[i for i in range(n) if i>=len(records['cut']) or records['cut'][i]!=actual[i]]
        failed('장면 측정 스트림이 누락되거나 출력 프레임 전체와 맞지 않습니다.',dict(
            nframes=n,cut_records=len(records['cut']),cut_mismatch_count=len(mismatches),
            first_cut_mismatches=[dict(index=i,expected=list(actual[i]),
                measured=list(records['cut'][i]) if i<len(records['cut']) else None) for i in mismatches[:8]],
            missing_score_count=sum(i not in scores for i in range(n)),
            first_missing_scores=[i for i in range(n) if i not in scores][:8],
            first_invalid_scores=[i for i in range(n) if i in scores and not math.isfinite(scores[i])][:8]))
    source_by_checksum = {}
    for _, pts, checksum in records['source']:
        source_by_checksum.setdefault(checksum, set()).add(pts)
    pts = []
    for _, _, checksum in actual:
        candidates = source_by_checksum.get(checksum, set())
        pts.append(next(iter(candidates)) if len(candidates) == 1 else None)
    if (set(time_bases) != {'native', 'all'} or first_output_tick is None or not native_ticks
            or any(i not in native_scores or not math.isfinite(native_scores[i]) for i in native_ticks)):
        failed('장면 측정의 원본 프레임 시간축 또는 점수가 누락됐습니다.')
    boundaries = set()
    for index, tick in native_ticks.items():
        if native_scores[index] > policy['scene_threshold']:
            position = Fraction(tick) * time_bases['native'] / time_bases['all']
            boundary = math.floor(position + Fraction(1, 2)) - first_output_tick
            if 0 < boundary < n: boundaries.add(boundary)
    cuts = [i for i in sorted(boundaries) if actual[i][2] != actual[i-1][2]]
    if declared_timing is not None:
        count = len(records['fps'][:n])
        if count not in (n-1, n) or count < 1:
            raise R.StepError('원본 영상의 끝 프레임 측정이 출력 예산과 다릅니다.')
        # The directory is already bound to source bytes and the full request
        # by _one. Always rewrite after this successful current measurement.
        R._photo_write_state(str(directory/'video-timing.json'), dict(
            request_key=directory.name, fps_frames=count, nframes=n,
            cut={k:cut[k] for k in ('src','start','duration','fps','video_timing')}))
    return paths, cuts, pts


def _measure(cut, paths, indices, directory, item, *, content=None, annotate=True, source_identity=None):
    """Use the canonical content and face/OCR detector, on exact output frames.

    `annotate=False` returns the clean content samples as the attachments —
    for callers that draw their own marks (text review) and never used the
    face-marked candidates this function would otherwise write.
    """
    from PIL import Image, ImageDraw
    import numpy as np
    if not item.get('framevision_cache'):
        _check_review_budget(item)
    if hasattr(paths, 'prepare'):
        paths.prepare(indices)
    bd = cut['band']
    with M.span('subject_content', publish=True):
        with Image.open(paths[indices[0]]) as im:
            width, height = im.size
        if content is None:
            def grays():
                for i in indices:
                    with Image.open(paths[i]) as im:
                        yield np.asarray(im.convert('L'))
            content = R._content_rect_over(grays(), bd['dark_max'], bd['black_frac'], bd['frame_dark_min'])
        elif (not _box(content, width, height) or any(type(v) is not int for v in content)):
            raise R.StepError('선택된 원본 알맹이 영역이 실제 프레임 밖이거나 잘못되었습니다.')
        x, y, w, h = content
        samples = []
        for n, i in enumerate(indices):
            with Image.open(paths[i]) as im:
                # A frame whose content rect is the whole picture is its own sample;
                # a real crop is written once under its sha256 (never a fixed name).
                if (x, y, w, h) == (0, 0, im.width, im.height) and im.format == 'PNG' and im.mode == 'RGB':
                    samples.append(Path(paths[i]))
                else:
                    samples.append(Path(R._frozen_png(im.convert('RGB').crop((x, y, x + w, y + h)), directory)))
    cache_options = (dict(cache_dir=item['framevision_cache'],
                          detector_identity=item.get('_detector_identity') or _detector_identity(item['framevision']))
                     if item.get('framevision_cache') else {})
    if R.resolve_review_policy(item.get('review_policy'))['provider'] == 'evolink':
        cache_options['before_measure'] = lambda:_check_review_budget(item)
    with M.span('subject_framevision', publish=True):
        measured = R._framevision_measure([str(p) for p in samples], w, h, item['framevision'], **cache_options)
    metadata, attachments = [], []
    for n, (i, path, faces) in enumerate(zip(indices, samples, measured['face_candidates'])):
        if faces and annotate:
            with Image.open(path) as image:
                image = image.convert('RGB'); draw = ImageDraw.Draw(image)
                for fid, (fx, fy, fw, fh) in enumerate(faces):
                    draw.rectangle((fx, fy, fx + fw, fy + fh), outline='lime', width=2)
                    draw.text((fx, max(0, fy - 12)), f'F{fid}', fill='lime', stroke_width=1, stroke_fill='black')
                annotated = R._frozen_png(image, directory)
        else:
            annotated = path  # nothing to mark (or caller marks): the sample itself is the candidate
        attachments.append({'path': str(annotated), 'mime': 'image/png'})
        metadata.append({'sample': n, 'frame_index': i, 'video_time': i / float(cut['fps']),
                         'source_time': float(cut['start']) + i / float(cut['fps']),
                         'faces': faces, 'content_size': [w, h]})
    measured.update(size=[width, height], content=list(content), measurement_version=3,
                    sample_times=[m['source_time'] for m in metadata])
    if cut.get('kind') == 'video' and len(cut.get('samples') or []) >= 2:
        import source_motion
        digest = source_identity or _sha(cut['src'])
        with M.span('subject_source_motion', publish=True):
            receipt = source_motion.measure(cut, content, digest, directory,
                                            before_measure=lambda:_check_review_budget(item))
        measured.update(motion=receipt['value'], source_motion=receipt, source_identity=digest)
    return measured, metadata, attachments


#: focus_selection_v1 답의 모양 — 서버 지시문(volcano_focus.selection_prompt)이 적은 JSON 그대로, 아래 `_decisions` 가 읽는 칸들.
#:   구독 AGY 에 이 스키마로 답을 받는다(글자로 감싼 JSON 의 이스케이프 실수 · 2026-10-21 신고 510306). 판정은 여전히 `_decisions`.
#:   null 칸은 JSON Schema 합집합 ['array','null'] — OpenAPI `nullable` 은 agy finish 검사기가 몰라 null 답을 거부한다(2026-10-22 같은 카드
#:   실측: nullable 4회 중 2회 거부 뒤 모델이 다시 답함 · 합집합 4회 중 거부 0회 · null 답 그대로 받음). 5분에 잘린 회차(20초 일·출력
#:   4,296 토큰 = 답 한 벌+finish 한 번 크기·결과 빈 답)는 그 거부 뒤 다시 답하지 않은 것으로 본다 — 그 회차 사건 줄은 남지 않아 추정이다.
FOCUS_ANSWER_SCHEMA = {
    'type': 'object', 'required': ['verdict', 'decisions', 'refine_intervals', 'summary'],
    'properties': {
        'verdict': {'type': 'string', 'enum': ['accepted', 'retry']},
        'decisions': {'type': 'array', 'items': {
            'type': 'object', 'required': ['sample', 'kind', 'face_ids', 'box', 'speaker', 'reason'],
            'properties': {
                'sample': {'type': 'integer'},
                'kind': {'type': 'string', 'enum': ['face', 'object', 'group', 'scene', 'unresolved']},
                'face_ids': {'type': ['array', 'null'], 'items': {'type': 'integer'}},
                'box': {'type': ['array', 'null'], 'items': {'type': 'number'}},
                'speaker': {'type': 'string', 'enum': ['visible', 'offscreen', 'silent', 'ambiguous']},
                'reason': {'type': 'string'}}}},
        'refine_intervals': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer'}}},
        'summary': {'type': 'string'}}}


def _decisions(answer, metadata, content, *, visual_subject=False):
    """Only real measured face IDs; object boxes are explicitly VLM detections."""
    if not isinstance(answer, dict) or answer.get('verdict') not in (None, 'accepted'):
        return None
    decisions = answer.get('decisions')
    if not isinstance(decisions, list) or len(decisions) != len(metadata):
        return None
    samples = {m['sample']:m for m in metadata}
    found = {}
    for d in decisions:
        if not isinstance(d, dict) or type(d.get('sample')) is not int:
            return None
        n = d['sample']
        if n in found or n not in samples:
            return None
        kind = d.get('kind'); speaker = d.get('speaker'); ids = d.get('face_ids')
        speakers = ('not_applicable',) if visual_subject else ('visible', 'offscreen', 'silent')
        if kind not in ('face', 'object', 'group', 'scene') or speaker not in speakers:
            return None
        if kind in ('object', 'scene') and 'face_ids' in d and ids is None:
            # No face is selected for these kinds. Normalize the parsed copy;
            # the bound raw reply and every actual selection field stay intact.
            ids = []
            d = dict(d, face_ids=ids)
        if not isinstance(d.get('reason'), str) or not d['reason'].strip() or not isinstance(ids, list):
            return None
        if any(type(i) is not int or not 0 <= i < len(samples[n]['faces']) for i in ids) or len(ids) != len(set(ids)):
            return None
        if kind in ('face', 'group'):
            if not ids or (kind == 'face' and len(ids) != 1):
                return None
            box = _union([samples[n]['faces'][i] for i in ids])
            engine = 'yunet-selected-ids'
        elif kind == 'object':
            if ids or not _box(d.get('box'), 1, 1):
                return None
            b = d['box']; box = [b[0] * content[2], b[1] * content[3], b[2] * content[2], b[3] * content[3]]
            engine = 'vlm-object-detection'
        else:
            if ids or speaker == 'visible':
                return None
            box = [0, 0, content[2], content[3]]; engine = 'explicit-scene-verdict'
        found[n] = dict(d, bbox=[box[0] + content[0], box[1] + content[1], box[2], box[3]], engine=engine)
    return [found[m['sample']] for m in metadata]


def _visual_subject(cut):
    scope = cut.get('review_scope')
    if scope is None:
        return False
    if (not isinstance(scope,dict) or scope.get('contract') != 'visual_subject_v1'
            or scope.get('source_audio') != 'excluded' or not isinstance(scope.get('prompt'),str)
            or not scope['prompt'].strip() or cut.get('focus_role') != 'subject'
            or cut.get('kind') != 'video'):
        raise R.StepError('시각 주피사체 검수는 원음을 제외한 subject 컷에만 적용합니다.')
    return True


def _review_visual_subject(cut, item, metadata, attachments, directory, headers, refinement):
    if len(metadata) != len(attachments) or not metadata:
        raise R.StepError('실측 프레임과 시각 검수 첨부 수가 다릅니다.')
    facts = dict(context=cut.get('context'),focus_role=cut['focus_role'],scope=cut['review_scope'],
        start=cut['start'],duration=cut['duration'],fps=cut['fps'],samples=metadata,refinement=refinement)
    binding = dict(facts,images=[_sha(a['path']) for a in attachments])
    key = hashlib.sha256(json.dumps(binding,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    config = copy.deepcopy(item['photo_review'])
    config.update(index=0,qc_contract='visual_subject_v1',binding=binding,
        prompt=cut['review_scope']['prompt']+'\nMeasured sample metadata: '+json.dumps(facts,ensure_ascii=False),
        images=[dict(url=R._file_uri(a['path']),mime=a['mime']) for a in attachments],
        image_labels=[f'sample={m["sample"]}:measured_candidate' for m in metadata],
        n_candidates=len(attachments),out=str(directory/('visual-'+key+'.json')))
    import subject_tracking_evidence as TE
    import sys
    config, relation_contract = TE.question_contract(sys.modules[__name__], config)
    indices=[m['frame_index'] for m in metadata]
    def accepted(answer, selected):
        return (_decisions(answer,selected,[0,0,*metadata[0]['content_size']],visual_subject=True) is not None
                and _refine_frames(answer,indices) is not None
                and (not relation_contract or TE.relations(answer,selected) is not None)
                and all(set(interval).issubset({m['sample'] for m in selected})
                        for interval in answer.get('refine_intervals') or []))

    def call(job, selected, allow):
        answer = R.image_qc([job],headers,retry=1,claude=job.get('claude'),
            allow_provider=allow,review_policy=item.get('review_policy'),client=item.get('review_client'),
            client_replies=item.get('focus_review_replies'),review_budget=item.get('_review_budget'),
            result_validator=lambda job,answer:accepted(answer,selected))['0']
        if isinstance(answer,dict):
            answer = dict(answer)
            answer.pop('_tracking_relation_contract',None)
            if relation_contract and accepted(answer,selected):
                answer['_tracking_relation_contract'] = TE.CONTRACT
        return answer

    allow = item.get('saved_reviews_only') is not True
    policy = R.resolve_review_policy(item.get('review_policy'))
    if policy['provider'] != 'evolink' or not any(config.get(k) is not None for k in ('max_media_bytes','max_request_bytes')):
        return call(config,metadata,allow)
    images = [(R._fetch_b64(im['url']),im['mime']) for im in config['images']]
    _,media,size = R._image_request_size(config,images)
    if R._image_request_fits(config,media,size):
        return call(config,metadata,allow)
    # Never replace a previously accepted or ambiguous paid whole-question
    # receipt with a new split question. Inspect that receipt without dispatch.
    prior = call(config,metadata,False)
    if prior.get('code') != 'review_receipt_missing':
        return prior
    # Keep every original pixel and every adjacent transition. The overlap is
    # a semantic requirement (two neighboring samples), not a provider limit.
    # Use the declared transport byte caps only; no new retry/rate constants.
    # Google inline guidance: https://ai.google.dev/gemini-api/docs/image-understanding
    # EvoLink-specific concurrency/cooldown numbers were not published in the
    # available model spec; existing review budget/refusal controls still apply.
    plans = []; begin = 0
    while begin < len(metadata):
        chosen = None
        minimum = min(begin + 2,len(metadata))
        for stop in range(minimum,len(metadata)+1):
            selected = metadata[begin:stop]
            batch_facts = dict(facts,samples=selected,all_samples=metadata,
                sample_id_scope='global; decide supplied samples; overlapping neighbors preserve transitions')
            job = dict(config,prompt=cut['review_scope']['prompt']+(TE.INSTRUCTION if relation_contract else '')+'\nMeasured sample metadata: '+json.dumps(batch_facts,ensure_ascii=False),
                images=config['images'][begin:stop],image_labels=config['image_labels'][begin:stop],
                n_candidates=stop-begin)
            _,media,size = R._image_request_size(job,images[begin:stop])
            if not R._image_request_fits(job,media,size):
                break
            digest = R._image_review_key(job,images[begin:stop],job.get('claude'))
            job['out'] = config['out']+'.batch_'+digest+'.json'
            chosen = (stop,job,selected)
        if chosen is None:
            raise R.StepError('원본 해상도의 인접 화면 검수 단위가 요청 크기 상한을 넘습니다. 원본·검수 기록을 보존했고 새 요청은 보내지 않았습니다.')
        stop,job,selected = chosen
        plans.append((job,selected))
        if stop == len(metadata):
            break
        begin = stop-1
    decisions = {}; intervals = []; batches = []; anchor_relations = []
    for job,selected in plans:
        answer = call(job,selected,allow)
        if not accepted(answer,selected):
            return answer
        for decision in answer['decisions']:
            number = decision['sample']
            previous = decisions.get(number)
            if previous is not None and any(previous.get(k) != decision.get(k) for k in ('kind','face_ids','box','speaker')):
                return dict(verdict='unresolved',code='visual_batch_overlap_disagrees',
                    reason='인접 검수 묶음의 같은 화면 선택이 달라 원본과 각 검수 답을 보존했습니다.',decisions=list(decisions.values()))
            decisions.setdefault(number,decision)
        if relation_contract:
            anchor_relations.extend(answer['anchor_relations'])
        for interval in answer.get('refine_intervals') or []:
            if interval not in intervals:
                intervals.append(interval)
        batches.append(dict(samples=[m['sample'] for m in selected],request_sha256=answer.get('request_sha256')))
    return dict(verdict='accepted',decisions=[decisions[m['sample']] for m in metadata],
                refine_intervals=intervals,batches=batches,
                **({'anchor_relations':anchor_relations,'_tracking_relation_contract':TE.CONTRACT} if relation_contract else {}))



@M.span('subject_review', publish=True)
def _review(cut, item, metadata, attachments, directory, headers, refinement=False, *, timeline=None):
    if _visual_subject(cut):
        return _review_visual_subject(cut,item,metadata,attachments,directory,headers,refinement)
    config = copy.deepcopy(item['photo_review'] if cut.get('kind') == 'image' else item['video_review'])
    facts = json.dumps({'context': cut.get('context'), 'focus_role': cut.get('focus_role'),
                       'samples': metadata, 'refinement': refinement}, ensure_ascii=False)
    if cut.get('kind') == 'image':
        config['prompt'] += '\nMeasured sample metadata: ' + facts
        job = dict(config, index=0, qc_contract='focus_selection_v1',
                   images=[{'url': R._file_uri(a['path']), 'mime': a['mime']} for a in attachments],
                   n_candidates=len(attachments), out=str(directory / ('review_refined.raw.json' if refinement else 'review.raw.json')))
        return R.image_qc([job], headers, retry=1, claude=config.get('claude'),
                          allow_provider=item.get('saved_reviews_only') is not True,
                          review_policy=item.get('review_policy'), client=item.get('review_client'),
                          client_replies=item.get('focus_review_replies'), review_budget=item.get('_review_budget'),
                          # The video and visual branches already bound refine_intervals to the measured samples.
                          # A photo has one sample, so the only valid list is [] — a copied [[0,1]] must be rejected
                          # here, before it is saved as a complete receipt and reused forever (10-01 trap).
                          result_validator=lambda job, answer: (_decisions(answer, metadata, [0, 0, *metadata[0]['content_size']]) is not None
                              and _refine_frames(answer, [m['frame_index'] for m in metadata]) is not None))['0']
    proxy = str(directory / 'review.mp4')
    def expand(value):
        if isinstance(value, str): return value.replace('@@SRC@@', cut['src']).replace('@@OUT@@', proxy)
        if isinstance(value, list): return [expand(v) for v in value]
        if isinstance(value, dict): return {k: expand(v) for k, v in value.items()}
        return value
    config = expand(config)
    config['path'] = cut['src']; config['out'] = proxy
    argv = config['shrink_argv']
    start, duration = float(cut['start']), float(cut['duration'])
    trim = cut.get('seek_mode') == 'trim'
    timeline = timeline if timeline is not None else _source_timeline(cut, directory)
    origin = timeline['origin']
    if not trim:
        argv[1:1] = ['-copyts']
        pos = argv.index('-i')
        argv[pos:pos] = ['-ss', str(start)]
    argv[-1:-1] = ['-t', str(duration), '-frames:v', str(round(duration*float(cut['fps'])))]
    # Explicit trim/redub grids keep their existing, declared frame contract.
    # Ordinary source seeks use exactly the same common-origin phase as _frames.
    timing = (f'trim=start={start:.12g}:end={start+duration:.12g},setpts=PTS-STARTPTS,'
              f"fps={float(cut['fps']):.12g},setpts=PTS-STARTPTS" if trim else
              f"setpts=PTS-round({start+origin:.12g}/TB),fps={float(cut['fps']):.12g}")
    declared_timing = _video_timing(cut)
    if declared_timing is not None:
        try:
            measured = json.loads((directory/'video-timing.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise R.StepError('재더빙 영상의 현재 프레임 측정이 없습니다.') from exc
        count = round(duration*float(cut['fps']))
        if (not isinstance(measured, dict) or measured.get('request_key') != directory.name
                or measured.get('cut') != {k:cut[k] for k in ('src','start','duration','fps','video_timing')}
                or measured.get('nframes') != count or type(measured.get('fps_frames')) is not int
                or measured['fps_frames'] not in (count-1, count) or measured['fps_frames'] < 1):
            raise R.StepError('재더빙 영상의 프레임 측정이 현재 요청과 다릅니다.')
        if measured['fps_frames'] == count-1:
            timing = declared_timing
    if '-vf' in argv:
        pos = argv.index('-vf') + 1
        if re.search(r'(^|,)\s*fps\s*=', argv[pos]):
            raise R.StepError('영상 검토 템플릿이 별도 fps를 선언했습니다. 같은 fps 계약으로 다시 요청하세요.')
        argv[pos] = timing + ',' + argv[pos]
    else:
        argv[-1:-1] = ['-vf', timing]
    audio = (f'atrim=start={start:.12g}:end={start+duration:.12g},asetpts=PTS-STARTPTS' if trim else
             f'asetpts=PTS-round({start+origin:.12g}/TB)')
    if '-af' in argv:
        pos = argv.index('-af') + 1; argv[pos] = audio + ',' + argv[pos]
    else:
        argv[-1:-1] = ['-af', audio]
    policy = R.resolve_review_policy(item.get('review_policy'))
    resolved_headers = None if item.get('saved_reviews_only') is True or policy['provider'] == 'client' else (headers() if callable(headers) else headers)
    proxy_cache = directory / 'review.proxy.json'
    try: receipt = json.loads(proxy_cache.read_text(encoding='utf-8'))
    except (OSError, ValueError): receipt = None
    if not R.video_proxy_valid(config, receipt):
        _check_review_budget(item)
        receipt = R.prepare_video_proxy(config)
        R._photo_write_state(str(proxy_cache), receipt)
    config['prepared_proxy'] = receipt
    return _review_batches(config, cut, metadata, attachments, directory, resolved_headers, refinement,
                           saved_reviews_only=item.get('saved_reviews_only') is True,
                           review_policy=item.get('review_policy'), client=item.get('review_client'),
                           client_replies=item.get('focus_review_replies'), review_budget=item.get('_review_budget'))


def _review_batches(config, cut, metadata, attachments, directory, headers, refinement, *, saved_reviews_only=False,
                    review_policy=None, client_replies=None, review_budget=None, client=None):
    """Lossless, exact-byte candidate batches, each with the full cut video/audio.

    Sample IDs and refinement intervals remain global across requests. Accepted
    batches are durable; execution resume pays only for remaining candidates.
    """
    context = R.current_review_context()
    review_policy = R.resolve_review_policy(review_policy)
    if 'replies' in context or client_replies is None: client_replies = context.get('replies')
    if context or review_budget is None: review_budget = context.get('budget')
    client = R.resolve_review_client(client)
    if len(metadata) != len(attachments):
        raise R.StepError('실측 후보와 첨부 그림 수가 다릅니다.')
    indices = [m['frame_index'] for m in metadata]
    combined = []; intervals = []; begin = 0
    def request(end):
        job = copy.deepcopy(config)
        facts = {'context':cut.get('context'), 'focus_role':cut.get('focus_role'),
                 'samples':metadata[begin:end], 'all_samples':metadata,
                 'decision_sample_ids':[m['sample'] for m in metadata[begin:end]],
                 'previous_decisions':combined, 'refinement':refinement,
                 'sample_id_scope':'global; decide supplied samples only; refine_intervals may cross batches'}
        job['body']['contents'][0]['parts'].append({'text':'Measured sample metadata: '+json.dumps(facts, ensure_ascii=False)})
        job['attachments'] = attachments[begin:end]
        return job
    image_digests = {}
    def request_key(job):
        for image in job['attachments']:
            if image['path'] not in image_digests:
                image_digests[image['path']] = _sha(image['path'])
        recipe = {'config':R.review_semantic_config(job),
                  'images':[image_digests[a['path']] for a in job['attachments']]}
        return hashlib.sha256(json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    # A host request references local media; Gemini's inline/base64 limits do
    # not describe that transport. Preserve any exact old split questions
    # (including pending/failed receipts), then ask all remaining samples once.
    # The existing client contract keeps unreadable evidence pending; there is
    # no declared model-context capacity from which to invent another batch cap.
    # ★시간 상한을 넘긴 질문은 반으로 나눠 묻는다(2026-10-21 쇼핑 shop_cuts 신고 — 그림 44장 한 호출이 학생 PC 에서
    #   272~331초로 AGY 상한 300초를 4번 다 넘겼고, «다시» 때마다 같은 44장이 같은 크기로 다시 나가 수렴하지 않았다).
    #   고정 장수 상한은 두지 않는다 — 같은 44장이 맥미니24g agy 1.4.3 에서는 61초(12·24장은 29초)라 기계마다 다르고 문서 숫자도
    #   없다. 그 기계에서 실제로 시간 초과(AGY_TIMEOUT 영수증)가 난 질문만 반씩 줄인다(줄일 때마다 범위가 줄어 log2(장수) 번 안에
    #   끝난다). 줄인 크기는 그 컷의 남은 표본에도 쓴다. 새 질문은 사람이 그 컷에 «다시» 를 알린 범위에서만 낸다 — 그 밖에서는
    #   이미 물은 반쪽 질문만 따라간다(자동 재요청 없음). 판정은 영수증(사실)에서만 다시 유도하므로 이어 하기마다 같은 묶음이 나온다.
    recorded = set()
    if review_policy['provider'] == 'client':
        recorded = {match.group(1) for path in directory.glob('review_batch_*.json*')
                    if (match := re.fullmatch(r'review_batch_([0-9a-f]{64})\.json(?:\.client-request\.json)?', path.name))}
    def ran_out_of_time(batch_key):
        receipt = R._review_receipt_io_path(str(directory / ('review_batch_'+batch_key+'.json')) + '.client-receipt.json')
        try:
            with open(receipt, encoding='utf-8') as stream: saved = json.load(stream)
        except (OSError, ValueError): return False
        if not isinstance(saved, dict) or not isinstance(saved.get('provider_evidence'), dict): return False
        result = saved['provider_evidence'].get('result')
        return (saved.get('outcome') == 'pending' and saved.get('attempted') is True
                and isinstance(result, dict) and result.get('code') == 'AGY_TIMEOUT')
    halved_size = None   # 이번에 반으로 줄여 정한 묶음 크기 — 남은 표본도 그 크기로 묻는다(다음 묶음이 또 시간 초과로 한 판을 버리지 않게)
    def timed_out_sizes():
        """이 컷에서 시간 상한을 넘긴 질문들의 그림 장수(질문 글이 달랐던 앞 판의 것까지 — 영수증 옆 요청 기록에서 센다).
        ★10-23 회원 신고 516558: 실행기가 갱신되어 질문 글(답 스키마)이 바뀌자 지문이 달라져 «반으로 줄인 크기» 를 잃고 같은 컷의
          새 질문이 다시 40장(22장 → 42파일 · 32MB)으로 나갔다 — 시간 초과는 그 기계·그 장수의 사실이지 글 지문의 사실이 아니다."""
        sizes = []
        for path in directory.glob('review_batch_*.json.client-receipt.json'):
            found = re.fullmatch(r'review_batch_([0-9a-f]{64})\.json\.client-receipt\.json', path.name)
            if not found or not ran_out_of_time(found.group(1)):
                continue
            try:
                with open(R._review_receipt_io_path(str(directory / ('review_batch_' + found.group(1) + '.json.client-request.json'))),
                          encoding='utf-8') as stream:
                    images = json.load(stream).get('images')
            except (OSError, ValueError, AttributeError):
                continue
            if isinstance(images, list) and len(images) > 1:
                sizes.append(len(images))
        return sizes
    while begin < len(metadata):
        end = begin; job = None; key = None
        if review_policy['provider'] == 'client':
            end = len(metadata) if halved_size is None else min(len(metadata), begin + halved_size)
            job = request(end); key = request_key(job)
            if recorded and key not in recorded:
                for stop in range(end-1, begin, -1):
                    proposed = request(stop); proposed_key = request_key(proposed)
                    if proposed_key in recorded:
                        end = stop; job = proposed; key = proposed_key; break
            if key not in recorded and halved_size is None and (sizes := timed_out_sizes()):
                # 어차피 새로 내는 질문이다 — 이 컷에서 시간을 넘긴 가장 작은 질문의 반을 넘지 않게 낸다(같은 지문 갈래의 반 나누기와 같은 크기 규칙).
                halved_size = (min(sizes) + 1) // 2
                if end - begin > halved_size:
                    end = begin + halved_size; job = request(end); key = request_key(job)
            asking_again = R.review_retry_active()
            while end - begin > 1 and recorded and ran_out_of_time(key):
                half = begin + (end - begin + 1) // 2
                proposed = request(half); proposed_key = request_key(proposed)
                if not asking_again and proposed_key not in recorded: break
                end = half; job = proposed; key = proposed_key; halved_size = end - begin
        else:
            for stop in range(begin+1, len(metadata)+1):
                proposed = request(stop)
                media, size = R.video_request_sizes(proposed, config['out'])
                if ((config.get('max_media_bytes') and media > int(config['max_media_bytes'])) or
                        (config.get('max_request_bytes') and size > int(config['max_request_bytes']))):
                    break
                end = stop; job = proposed
        if job is None:
            exc = R.StepError('전체 컷 영상·음성과 원본 해상도 후보 한 장이 요청 상한을 넘습니다. 후보를 생략하거나 해상도를 낮추지 않았습니다.')
            exc.code = 'review_request_oversize'   # 같은 컷·같은 상한이면 다시 재도 같다 — local_focus 가 «다시» 대신 다른 길로 푼다.
            raise exc
        selected = metadata[begin:end]
        if key is None: key = request_key(job)
        cache = directory / ('review_batch_'+key+'.json')
        content = [0, 0, *metadata[0]['content_size']]
        def accepted(answer):
            return (_decisions(answer, selected, content) is not None and
                    _refine_frames(answer, indices) is not None)
        with R.review_receipt_lock(cache):
            saved = None
            try:
                saved = json.loads(cache.read_text(encoding='utf-8'))
                answer = saved.get('answer') if saved.get('request_key') == key else None
            except (OSError, ValueError, AttributeError): answer = None
            known = isinstance(saved,dict) and saved.get('request_key') == key
            if (known and not saved_reviews_only
                    and R.release_unfinished_review(cache, key, saved, R.unfinished_review(saved))):
                # 사람이 «다시» 를 알린 컷 — 결과 없이 끝난(끝을 모르는) 이 질문을 한 번 다시 묻는다(옛 기록은 옆에 보존).
                saved = None; answer = None; known = False
            if known and saved.get('outcome') in ('started','failed','refused'):
                if saved.get('outcome') == 'refused':
                    raise R.remember_review_refusal(R.ProviderRefusalError(saved['origin'],saved['reason_code'],saved['reason']))
                exc = R.StepError(saved.get('reason') or '앞선 영상 검수의 완료 여부를 확인할 수 없습니다. 같은 유료 요청은 자동 반복하지 않습니다.')
                exc.code = _http_failure_code(saved.get('code') or 'review_unknown_completion')
                raise exc
            if accepted(answer) or known and 'answer' in saved:
                M.event('subject_review', 'reused', key)
            else:
                if saved_reviews_only:
                    exc = R.StepError('같은 질문의 저장된 영상 검수 답이 없습니다. 새 모델 요청은 보내지 않았습니다.')
                    exc.code = 'review_receipt_missing'
                    raise exc
                if review_policy['provider'] == 'client':
                    prompt = '\n'.join(part['text'] for content in job['body']['contents'] for part in content['parts'] if 'text' in part)
                    # ★1초보다 짧은 컷은 영상 파일을 붙이지 않는다(2026-10-21 쇼핑 신고 510306). Gemini 는 영상을 초당 1장으로 뽑아 보므로
                    #   (공식 문서 «video understanding · 1 frame per second») 1초 미만 영상은 많아야 한 장 — 위 실측 후보 그림이 이미 그 화면이다.
                    #   그리고 그런 영상은 요청 전체를 400 INVALID_ARGUMENT 로 거절당한다(맥 agy 1.4.3 실측: 영상만 0.4·0.47초 400 · 0.3초 소리
                    #   포함 400 · 0.5·0.9·1.0·1.07초 통과). 소리(review.audio.wav)는 그대로 붙인다 — 화자 판정의 근거.
                    media = R.client_video_audio(config,directory)
                    # 길이를 모르는 컷은 1초 미만이라고 볼 근거가 없다 — 예전처럼 영상을 붙인다(실제 컷 render.focus_cuts 는 늘 싣는다).
                    attach_video = not (_number(cut.get('duration')) and float(cut['duration']) < 1.0) or not media.get('audio')
                    if not attach_video:
                        prompt += '\nThis cut is shorter than one second, so no video file is attached: judge from the measured candidate images and the attached audio.'
                    client_job = dict(prompt=prompt,qc_contract='focus_selection_v1',out=str(cache),answer_schema=FOCUS_ANSWER_SCHEMA,
                        images=[dict(a,label=f'sample={m["sample"]}:measured_candidate') for a,m in zip(job['attachments'],selected)],
                        binding={'request_key':key},**({'video':config['out']} if attach_video else {}),**media)
                    answer = R.client_review(client_job,replies=client_replies,validator=accepted,client=client)
                    R._photo_write_state(str(cache),{'request_key':key,'answer':answer,'outcome':'complete','engine':'client'})
                elif not R.http_headers(headers):
                    exc = R.StepError('모델 키가 없다 — 서버가 알려준 자리에 키를 넣어라')
                    exc.code = 'review_key_missing'; raise exc
                else:
                    attempts = {'reserved':0}
                    R._photo_write_state(str(cache),{'request_key':key,'outcome':'started'})
                    try:
                        answer = R.ask_video(dict(job,**({'_review_policy':review_policy,'_review_budget':review_budget,
                            '_review_attempts':attempts} if review_policy is not None else {})), headers)
                    except Exception as exc:
                        result = {'request_key':key,'outcome':'failed','code':_http_failure_code(getattr(exc,'code','review_unknown_completion')),'reason':str(exc)[:1200]}
                        if getattr(exc,'review_budget_blocked',None):
                            result.update(outcome='budget_blocked',review_budget_blocked=exc.review_budget_blocked)
                        if isinstance(exc,R.ProviderRefusalError):
                            result.update(outcome='refused',origin=exc.origin,reason_code=exc.reason_code,reason=exc.reason,
                                          request_sent=getattr(exc,'request_sent',True))
                        R._photo_write_state(str(cache),result)
                        raise
                    R._photo_write_state(str(cache), {'request_key':key, 'answer':answer,'outcome':'complete'})
        if not isinstance(answer, dict): return answer
        requested = answer.get('refine_intervals') or []
        if _refine_frames(answer, indices) is None:
            return answer
        intervals.extend(requested)
        decisions = answer.get('decisions')
        if not accepted(answer):
            return dict(answer, decisions=combined+(decisions if isinstance(decisions,list) else []), refine_intervals=intervals)
        combined.extend(decisions); begin = end
    return {'verdict':'accepted', 'decisions':combined, 'refine_intervals':intervals}


def _flow(before, after, box, policy):
    """Actual image evidence only. Reject uncertain motion instead of interpolating."""
    import cv2
    import numpy as np
    if np.array_equal(before, after):
        return list(box)
    x, y, w, h = box
    mask = np.zeros_like(before)
    mask[max(0, math.ceil(y)):min(before.shape[0], math.floor(y + h)),
         max(0, math.ceil(x)):min(before.shape[1], math.floor(x + w))] = 255
    minimum = policy['min_points']; error = policy['max_error_px']
    points = cv2.goodFeaturesToTrack(before, maxCorners=max(100, minimum * 4), qualityLevel=.01, minDistance=3, mask=mask)
    if points is None or len(points) < minimum:
        return None
    nxt, status, _ = cv2.calcOpticalFlowPyrLK(before, after, points, None)
    if nxt is None:
        return None
    back, valid, _ = cv2.calcOpticalFlowPyrLK(after, before, nxt, None)
    if back is None:
        return None
    good = ((status[:, 0] == 1) & (valid[:, 0] == 1) &
            (np.linalg.norm(back[:, 0] - points[:, 0], axis=1) <= error))
    if good.sum() < minimum or good.mean() < policy['min_inlier_fraction']:
        return None
    matrix, inliers = cv2.estimateAffinePartial2D(points[good], nxt[good], method=cv2.RANSAC, ransacReprojThreshold=error)
    if matrix is None or inliers is None or inliers.mean() < policy['min_inlier_fraction']:
        return None
    corners = np.array([[x, y], [x + w, y], [x, y + h], [x + w, y + h]], dtype='float64')
    mapped = corners @ matrix[:, :2].T + matrix[:, 2]
    low = mapped.min(axis=0); high = mapped.max(axis=0)
    result = [float(low[0]), float(low[1]), float(high[0] - low[0]), float(high[1] - low[1])]
    return result if _box(result, before.shape[1], before.shape[0]) else None


def _clamp_subpixel(box, bounds, tolerance=1.0):
    """Clamp sub-pixel overshoot into the content; leave real overshoot for the server to judge.

    Detector and optical-flow boxes carry sub-pixel noise; a group box spanning
    the whole content band exceeded it by 0.01-0.12px on 11 of 48 frames and the
    server rejected the cut as `tracking_bbox_invalid` (2026-09-12 실측).
    """
    try:
        x, y, w, h = (float(v) for v in box)
        bx, by, bw, bh = (float(v) for v in bounds)
    except (TypeError, ValueError):
        return box
    over = max(bx - x, by - y, (x + w) - (bx + bw), (y + h) - (by + bh))
    if over <= 0 or over >= tolerance:
        return box
    left, top = max(x, bx), max(y, by)
    right, bottom = min(x + w, bx + bw), min(y + h, by + bh)
    if right - left <= 0 or bottom - top <= 0:
        return box
    return [left, top, right - left, bottom - top]


@M.span('subject_tracking', publish=True)
def _track(paths, indices, decisions, cuts, pts, cut, policy, content=None):
    from contextlib import nullcontext
    with paths.tracking() if hasattr(paths, 'tracking') else nullcontext():
        return _track_pixels(paths, indices, decisions, cuts, pts, cut, policy, content)


def _track_pixels(paths, indices, decisions, cuts, pts, cut, policy, content=None):
    import numpy as np
    from PIL import Image
    anchors = dict(zip(indices, decisions)); track = []; refine = set(); previous = None; bbox = None
    def gray(index):
        if hasattr(paths, 'gray_at'):
            return paths.gray_at(index)
        with Image.open(paths[index]) as image:
            return np.asarray(image.convert('L'))
    kind = None; speaker = None
    for i in range(len(paths)):
        frame = None
        predicted = None
        if i and i not in cuts and bbox is not None:
            if kind == 'scene':
                predicted = bbox
            else:
                if previous is None:
                    previous = gray(i-1)
                frame = gray(i)
                predicted = _flow(previous, frame, bbox, policy['tracking'])
        boundary = i in cuts
        if i in anchors:
            decision = anchors[i]; selected = decision['bbox']
            if i and not boundary:
                inconsistent = (predicted is None or max(abs(a-b) for a, b in zip(predicted, selected)) > policy['tracking']['max_error_px']
                                or kind != decision['kind'] or speaker != decision['speaker'])
                if inconsistent:
                    left = max((n for n in indices if n < i), default=0)
                    if i - left > 1: refine.update(range(left, i + 1))
                    elif bbox is not None:
                        # Both adjacent frames have explicit selections, so a
                        # tracking residual no longer means missing evidence.
                        # Keep a camera step for disjoint selected regions;
                        # overlapping detector jitter is not a scene cut.
                        boundary = (min(bbox[0]+bbox[2],selected[0]+selected[2]) <= max(bbox[0],selected[0])
                                    or min(bbox[1]+bbox[3],selected[1]+selected[3]) <= max(bbox[1],selected[1]))
            bbox = selected; kind = decision['kind']; speaker = decision['speaker']
        else:
            bbox = predicted
            if bbox is None:
                left = max((n for n in indices if n < i), default=0)
                right = next((n for n in indices if n > i), len(paths) - 1)
                refine.update(range(left, right + 1))
        if content is not None and bbox is not None:
            bbox = _clamp_subpixel(bbox, content)
        track.append({'frame_index': i, 't': float(cut['start']) + i / float(cut['fps']),
                      'source_pts': pts[i], 'bbox': bbox, 'cut': boundary})
        previous = frame
    return track, refine


@M.span('subject_object_review', publish=True)
def _object_review(item, cut, paths, indices, decisions, content, directory, headers):
    """Verify all selected objects, then at most one changed crop per failed sample."""
    from PIL import Image, ImageDraw
    objects = [(n, d) for n, d in enumerate(decisions) if d['kind'] == 'object']
    if not objects:
        return None
    config = item.get('object_review')
    if not isinstance(config, dict) or not config.get('prompt'):
        return {'status':'unresolved','code':'object_review_missing','reason':'물체 검수 계약이 없습니다.','decisions':[]}

    def complete(answer, metadata):
        if not isinstance(answer, dict) or answer.get('verdict') not in ('accepted','retry'):
            return False
        expected = {m['sample'] for m in metadata}; ds = answer.get('decisions')
        if not (isinstance(ds,list) and len(ds)==len(expected) and all(isinstance(d,dict) for d in ds)):
            return False
        seen = set()
        for d in ds:
            n = d.get('sample')
            if (type(n) is not int or n not in expected or n in seen or type(d.get('accepted')) is not bool
                    or not isinstance(d.get('reason'),str) or not 0 < len(d['reason'].strip()) <= 1200):
                return False
            seen.add(n)
            if 'candidate_box' in d and (d.get('coordinate_space') != 'content_normalized_xywh'
                    or type(d.get('same_subject')) is not bool or not _box(d['candidate_box'],1,1)):
                return False
        return seen == expected

    def review(selected, round_index=0, previous=None):
        units = []; target = directory if not round_index else directory / 'object_correction'
        target.mkdir(parents=True,exist_ok=True)
        x,y,w,h = content
        for n,d in selected:
            b = d['bbox']; frame = indices[n]
            with Image.open(paths[frame]) as im:
                image = im.convert('RGB')
                crop_size = [max(1,math.ceil(b[2])),max(1,math.ceil(b[3]))]
                crop = Path(R._frozen_png(image.resize(tuple(crop_size),Image.Resampling.LANCZOS,
                                                       box=(b[0],b[1],b[0]+b[2],b[1]+b[3])),target))
                image = image.crop((x,y,x+w,y+h)); draw = ImageDraw.Draw(image)
                draw.rectangle((b[0]-x,b[1]-y,b[0]+b[2]-x,b[1]+b[3]-y),outline='lime',width=2)
                whole = Path(R._frozen_png(image,target))
            metadata = {'sample':n,'frame_index':frame,'bbox_source_pixels':b,
                        'content_origin_source_xy':[x,y],'content_size':[w,h],
                        'box_content_normalized_xywh':[(b[0]-x)/w,(b[1]-y)/h,b[2]/w,b[3]/h],
                        'crop_size':crop_size,'crop_sampling':'fractional_source_box'}
            if previous:
                metadata['previous_review'] = previous[n]
                metadata['original_bbox_source_pixels'] = next(original['bbox'] for sample,original in objects if sample==n)
            units.append({'metadata':metadata,'images':[{'url':R._file_uri(p),'mime':'image/png'} for p in (whole,crop)],
                          'labels':[f'sample={n}:source_with_box',f'sample={n}:actual_crop']})
            image.close()
            del image, draw
        instruction = ('\nAttachment labels identify the sample and source/crop role; do not use attachment numbers as sample IDs. '
            'For a correctable false decision only, you may return candidate_box=[x,y,w,h], '
            'coordinate_space="content_normalized_xywh", same_subject=true only when it is the SAME selected object. '
            'Never choose a different object. A correction remains unverified until its changed actual crop is checked.')
        if round_index:
            instruction += '\nThis is the single independent check of the changed crop. original_bbox_source_pixels identifies the originally selected object; confirm the changed crop preserves that SAME object. Compare actual images; a previous proposal is not proof. Do not propose another correction.'
        def prompt_for(metadata):
            facts = {'context':cut.get('context'),'samples':metadata,'correction_round':round_index}
            return config['prompt'] + instruction + '\nMeasured object crops: ' + json.dumps(facts,ensure_ascii=False)
        job = dict(config,index=0,out=str(target/'object_review.json'),qc_contract='focus_object_v1')
        return R.image_qc_batches(job,units,headers,prompt_for=prompt_for,result_validator=complete,
                                  allow_provider=item.get('saved_reviews_only') is not True,
                                  review_policy=item.get('review_policy'), client=item.get('review_client'),
                                  client_replies=item.get('focus_review_replies'), review_budget=item.get('_review_budget'))

    try:
        answer = review(objects)
    except R.StepError as exc:
        if isinstance(exc,R.ClientReviewPending) or getattr(exc,'review_budget_blocked',None): raise
        return {'status':'unresolved','code':'provider_refused' if isinstance(exc,R.ProviderRefusalError) else _http_failure_code(getattr(exc,'code','object_review_failed')),
                'reason':str(exc)[:1200],'decisions':[]}
    metadata = [{'sample':n} for n,_ in objects]
    result = {'status':'unresolved','code':answer.get('code') or 'object_review_unresolved',
              'reason':answer.get('reason') or '물체 좌표에 대한 별도 자르기 검증을 완료하지 못했습니다.',
              'decisions':answer.get('decisions') or [],'batches':answer.get('batches') or [],'correction_rounds':0}
    if not complete(answer,metadata):
        return result
    rejected = {d['sample']:d for d in answer['decisions'] if not d['accepted']}
    if not rejected:
        # The contract defines uncertainty as accepted=false on a sample; every
        # sample was checked and accepted, so a batch-level 'retry' contradicts
        # the decisions and is recorded, not obeyed (2026-09-12 실측: 인물형
        # 사물 컷 57표본 전부 accepted 인데 묶음 둘이 retry 라 영영 unresolved 였다).
        return dict(result,status='accepted',code=None,reason=None,corrected_boxes={},
                    **({'verdict_conflict':answer['verdict']} if answer['verdict']!='accepted' else {}))
    # ★한 표본이 고칠 수 없다고 전체 교정을 포기하지 않는다 (2026-09-12 실측: 22개 거절 중
    #   13개에 모델의 candidate_box 가 있었는데 첫 번째 고칠 수 없는 표본에서 return 해
    #   교정 라운드가 0회였고, 사유도 «검증을 완료하지 못했습니다» 한 줄뿐이었다).
    corrections = []; uncorrectable = {}
    for n,d in objects:
        if n not in rejected:
            continue
        proposal = rejected[n]; b = proposal.get('candidate_box')
        if proposal.get('same_subject') is not True or not _box(b,1,1):
            uncorrectable[n] = str(proposal.get('reason') or ''); continue
        x,y,w,h = content
        box = [x+b[0]*w,y+b[1]*h,b[2]*w,b[3]*h]
        if max(abs(a-b) for a,b in zip(box,d['bbox'])) < 1e-9:
            uncorrectable[n] = str(proposal.get('reason') or ''); continue
        corrections.append((n,dict(d,bbox=box)))
    def unresolved_reason(extra=''):
        first = next(iter(uncorrectable.values()), '') if uncorrectable else ''
        # No usable same-subject proposal is not proof the source is unusable.
        # Keep the negative verdict and its evidence without inferring absence.
        return (f"물체 검수에서 {len(rejected)}/{len(objects)} 표본이 거절됐습니다"
                + (f" — 그중 {len(uncorrectable)}개는 같은 대상에 적용할 변경된 교정안이 없습니다" if uncorrectable else '')
                + (f" (첫 사유: {first[:300]})" if first else '') + extra
                + ". 원본·선택 상자·검수 사유를 확인한 뒤 필요한 선택 또는 소재를 수정하세요. "
                  "같은 검사를 자동 반복하지 않습니다.")
    if not corrections:
        return dict(result,reason=unresolved_reason(),uncorrectable=sorted(uncorrectable))
    try:
        checked = review(corrections,1,rejected)
    except R.StepError as exc:
        if isinstance(exc,R.ClientReviewPending) or getattr(exc,'review_budget_blocked',None): raise
        return dict(result,correction_rounds=1,code='provider_refused' if isinstance(exc,R.ProviderRefusalError) else _http_failure_code(getattr(exc,'code','object_correction_failed')),
                    reason=str(exc)[:1200])
    result.update(correction_rounds=1,correction_review=checked)
    corrected_ok = (complete(checked,[{'sample':n} for n,_ in corrections])
                    and all(d['accepted'] for d in checked['decisions']))
    boxes = {str(n):d['bbox'] for n,d in corrections}
    if corrected_ok and not uncorrectable:
        return dict(result,status='accepted',code=None,reason=None,corrected_boxes=boxes,
                    **({'verdict_conflict':checked['verdict']} if checked.get('verdict')!='accepted' else {}))
    return dict(result,reason=unresolved_reason(f"; 교정 검수 {len(corrections)}개 {'통과' if corrected_ok else '실패'}"),
                uncorrectable=sorted(uncorrectable),**({'corrected_boxes':boxes} if corrected_ok else {}))


def _refine_frames(answer, indices):
    if not isinstance(answer, dict):
        return None
    intervals = answer.get('refine_intervals', [])
    if not isinstance(intervals, list):
        return None
    frames = set()
    for interval in intervals:
        if (not isinstance(interval, list) or len(interval) != 2 or
                any(type(v) is not int for v in interval) or not 0 <= interval[0] < interval[1] < len(indices)):
            return None
        frames.update(range(indices[interval[0]], indices[interval[1]] + 1))
    return frames


def _cached_complete(row, cut, key, source_sha):
    if not isinstance(row, dict) or row.get('_recipe') != key or row.get('focus_status') != 'accepted':
        return False
    size = row.get('size'); subject = row.get('framing_subject'); scene = row.get('scene_evidence')
    if (not isinstance(size, list) or len(size) != 2 or not all(_number(v) and v > 0 for v in size)
            or not isinstance(subject, dict) or subject.get('complete') is not True
            or not _box(subject.get('bbox'), *size) or row.get('focus_key') != cut['focus_key']
            or row.get('source_identity') != source_sha or not isinstance(scene, dict)):
        return False
    n = 1 if cut.get('kind') == 'image' else round(float(cut['duration']) * float(cut['fps']))
    track = subject.get('track'); evidence = subject.get('selection_evidence')
    if (not isinstance(evidence, dict) or not isinstance(evidence.get('decisions'), list)
            or not evidence['decisions']
            or any(not isinstance(d, dict) or d.get('kind') not in ('face','object','group','scene')
                   for d in evidence['decisions'])
            or not isinstance(track, list) or len(track) != n
            or (subject.get('kind') == 'object' or any(d['kind'] == 'object' for d in evidence['decisions']))
                and evidence.get('object_verified') is not True):
        return False
    if (scene.get('status') != 'ok' or scene.get('source_identity') != source_sha or scene.get('nframes') != n
            or scene.get('start') != float(cut['start']) or scene.get('fps') != float(cut['fps'])):
        return False
    return all(isinstance(t, dict) and type(t.get('frame_index')) is int and t['frame_index'] == i
               and _number(t.get('t')) and abs(t['t'] - (float(cut['start']) + i / float(cut['fps']))) < 1e-6
               and _box(t.get('bbox'), *size) for i, t in enumerate(track))


def _detector_identity(root):
    """Fingerprint the installed detector/model bytes and effective runtime knobs."""
    return R._framevision_identity(root)


def _legacy_accepted(cut, item, recipe, key, source_sha):
    """One exact deployed recipe only; never scan or migrate failed evidence."""
    compat = item.get('accepted_cache_compatibility')
    if (not isinstance(compat,dict) or compat.get('provenance') != 'f6602ab294d4b33a7bcfc0d3ef108a9583165206'
            or type(compat.get('algorithm')) is not int or compat['algorithm'] != 3 or ALGORITHM_VERSION != 3
            or compat.get('policy') != recipe['policy'] or not isinstance(compat.get('legacy_focus_keys'),dict)):
        return None
    old_focus = compat['legacy_focus_keys'].get(str(cut['card']))
    if any(not isinstance(v,str) or re.fullmatch('[0-9a-f]{64}',v) is None
           for v in (old_focus,compat.get('selection_recipe'))):
        return None
    def controls(value):
        if isinstance(value,dict):
            return {k:('<prompt>' if k=='text' else controls(v)) for k,v in value.items()
                    if k not in ('prompt','max_media_bytes','max_request_bytes')}
        if isinstance(value,list):return [controls(v) for v in value]
        return value
    for field in ('photo_review','video_review','object_review'):
        if (not isinstance(compat.get(field),dict)
                or controls(R.review_semantic_config(compat[field])) != controls(R.review_semantic_config(item.get(field)))):
            return None
    old_cut = dict(cut,selection_recipe=compat['selection_recipe'],focus_key=old_focus)
    old_recipe = dict(recipe,cut=old_cut,algorithm=3,
                      **{k:compat[k] for k in ('policy','photo_review','video_review','object_review')})
    old_key = hashlib.sha256(json.dumps(old_recipe,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    try:
        row = json.loads((Path(item['out_dir'])/old_key/'accepted.json').read_text(encoding='utf-8'))
        if not _cached_complete(row,old_cut,old_key,source_sha):return None
        mapped = dict(row,focus_key=cut['focus_key'],_recipe=key)
        if not _cached_complete(mapped,cut,key,source_sha):return None
        if _sha(cut['src']) != source_sha:return None
        return mapped
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return None


def _duration_accepted(cut, item, recipe, key, source_sha, timeline):
    """One exact pre-timestamp producer recipe; duration is not review content."""
    if timeline is None or not _number(cut.get('source_duration')):
        return None
    # Before source-origin measurement, _src_facts published video length to
    # three decimals. Reconstruct only that known recipe, with the same source
    # bytes, question, sampling grid, cut key and complete acceptance.
    previous = round(timeline['source_end']-timeline['source_start'],3)
    if previous == cut['source_duration']:
        return None
    old_cut = dict(cut,source_duration=previous)
    old_recipe = dict(recipe,cut=old_cut)
    old_key = hashlib.sha256(json.dumps(old_recipe,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    try:
        row = json.loads((Path(item['out_dir'])/old_key/'accepted.json').read_text(encoding='utf-8'))
        if not _cached_complete(row,old_cut,old_key,source_sha): return None
        mapped = dict(row,_recipe=key)
        if not _cached_complete(mapped,cut,key,source_sha): return None
        return mapped
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return None


def _previous_visual_accepted(cut,item,recipe,key,source_sha):
    """Keep complete subject decisions; a visible-speaker choice is a different question."""
    if not _visual_subject(cut):return None
    previous_key=(item.get('visual_subject_previous_keys') or {}).get(str(cut['card']))
    if not isinstance(previous_key,str) or re.fullmatch('[0-9a-f]{64}',previous_key) is None:
        return None
    previous={k:v for k,v in cut.items() if k != 'review_scope'}
    previous['focus_key']=previous_key
    old_recipe=dict(recipe,cut=previous)
    old_key=hashlib.sha256(json.dumps(old_recipe,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    try:
        row=json.loads((Path(item['out_dir'])/old_key/'accepted.json').read_text(encoding='utf-8'))
        if not _cached_complete(row,previous,old_key,source_sha):return None
        decisions=row['framing_subject']['selection_evidence']['decisions']
        if any(d.get('speaker') not in ('silent','offscreen') for d in decisions):return None
        mapped=dict(row,focus_key=cut['focus_key'],_recipe=key)
        if _cached_complete(mapped,cut,key,source_sha) and _sha(cut['src']) == source_sha:return mapped
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        pass
    return None


def _check_review_budget(item):
    """Completed evidence is read first; only fresh work requires room to review."""
    policy = R.resolve_review_policy(item.get('review_policy'))
    if policy['provider'] != 'evolink':
        return
    context = R.current_review_context()
    ledger = (context.get('budget') if context else item.get('_review_budget')
              or item.get('review_budget') or str(Path(item.get('out_dir') or '.')/'review-budget.sqlite3'))
    R.review_budget_preflight(policy, ledger)


def _one(cut, item, headers, input_digests=None):
    if input_digests is None:
        with R._ArgvInputDigests() as owned:
            return _one(cut, item, headers, owned)
    try:
        return _one_measured(cut, item, headers, input_digests.digest)
    finally:
        # Includes accepted/migrated cache hits and native review handoffs.
        # The batch guard remains open until every parallel cut has finished.
        input_digests.check([cut['src']])


def _one_measured(cut, item, headers, source_digest):
    # Only the verified, fully derived grid is outside the semantic cut key.
    # Complete old frame sequences are unchanged; bad timing cannot hit cache.
    _video_timing(cut)
    visual_subject = _visual_subject(cut)
    semantic_cut = {k:v for k,v in cut.items() if k != 'video_timing'}
    source_sha = source_digest(cut['src']); policy = _policy(item)
    recipe = dict(cut=semantic_cut, policy=policy, video_review=R.review_semantic_config(item.get('video_review')),
                  photo_review=R.review_semantic_config(item.get('photo_review')),
                  object_review=R.review_semantic_config(item.get('object_review')),
                  framevision=item.get('framevision'), source_identity=source_sha,
                  detector=item.get('_detector_identity') or _detector_identity(item['framevision']),
                  algorithm=ALGORITHM_VERSION)
    key = hashlib.sha256(json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    directory = Path(item['out_dir']) / key; directory.mkdir(parents=True, exist_ok=True)
    with ExitStack() as execution:
        if visual_subject:
            execution.enter_context(R.review_receipt_lock(str(directory/'clock-execution')))
        return _one_locked(cut,item,headers,source_digest,source_sha,policy,recipe,key,directory,
                           visual_subject,semantic_cut,execution)


def _one_locked(cut,item,headers,source_digest,source_sha,policy,recipe,key,directory,
                visual_subject,semantic_cut,execution):
    if (directory/'frame-transaction.json').exists():
        with R.review_receipt_lock(str(directory/'frame-evidence.json')):
            _recover_frame_transaction(directory)
    if '_timeline_locks' in item:
        # Receipt OS locks deliberately do not wait. Same-batch cuts instead
        # share a bounded local single flight, then read the completed receipt.
        # This dictionary dies with the batch and cannot accumulate source keys.
        with item['_timeline_lock_guard']:
            lock = item['_timeline_locks'].setdefault(source_sha,threading.Lock())
        with lock:
            timeline = _source_timeline(cut, directory, source_sha)
    else:
        timeline = _source_timeline(cut, directory, source_sha)
    clock_recovered=False
    if visual_subject and (directory/'pre-review-clock-proof.json').exists():
        import subject_frame_clock as FC
        selected_clock,frame_directory=FC.select(R,directory,key,item.get('fresh_frame_clock'),execution)
        directory=frame_directory;cut=dict(cut,frame_clock=selected_clock);clock_recovered=True
    cache = directory / 'accepted.json'
    cached = None
    try:
        cached = json.loads(cache.read_text(encoding='utf-8'))
        valid_cached = _cached_complete(cached, cut, key, source_sha)
    except (OSError, ValueError, AttributeError):
        valid_cached = False
    if valid_cached:
        _check_source_pts([p.get('source_pts') for p in cached['framing_subject']['track']], cut, timeline)
        M.event('subject_selection', 'reused', key)
        # A pixel failure must not invalidate an already accepted semantic row.
        _accepted_motion(cached, cut, source_sha, directory)
        R._photo_write_state(str(cache), cached)
        return cached
    migrated = None if clock_recovered else (_duration_accepted(semantic_cut,item,recipe,key,source_sha,timeline)
                or _previous_visual_accepted(semantic_cut,item,recipe,key,source_sha)
                or _legacy_accepted(semantic_cut,item,recipe,key,source_sha))
    if migrated is not None:
        _check_source_pts([p.get('source_pts') for p in migrated['framing_subject']['track']], cut, timeline)
        M.event('subject_selection', 'reused', key)
        _accepted_motion(migrated, cut, source_sha, directory)
        R._photo_write_state(str(cache),migrated)
        return migrated
    frame_directory=directory
    if visual_subject and not clock_recovered:
        import subject_frame_clock as FC
        selected_clock,frame_directory=FC.select(R,directory,key,item.get('fresh_frame_clock'),execution)
        if selected_clock is not None:cut=dict(cut,frame_clock=selected_clock)
        if frame_directory != directory:
            # Recovered extraction AND all fresh questions stay in the proof's
            # namespace. Any later old-namespace paid record is ambiguous.
            directory=frame_directory;cache=directory/'accepted.json'
            try:
                cached=json.loads(cache.read_text(encoding='utf-8'))
                valid_cached=_cached_complete(cached,cut,key,source_sha)
            except (OSError,ValueError,AttributeError):valid_cached=False
            if valid_cached:
                _check_source_pts([p.get('source_pts') for p in cached['framing_subject']['track']],cut,timeline)
                _accepted_motion(cached,cut,source_sha,directory)
                return cached
    frame_item=dict(item)
    paths, cuts, pts = _frames_for_selection(cut, frame_directory, frame_item, policy,
        source_digest=source_digest, timeline=timeline,
        before_decode=lambda:_check_review_budget(item))
    if frame_item.get('_local_recovery_only'):item=dict(item,saved_reviews_only=True)
    stride = max(1, round(policy['sample_interval'] * float(cut['fps'])))
    indices = sorted(set(range(0, len(paths), stride)) | {len(paths)-1} | {i for c in cuts for i in (c-1, c)})
    final = None; reason = '모델이 피사체 선택을 완료하지 못했습니다.'
    measured = {}; answer = {}; track = []; metadata = []; round_index = 0; object_verified = None
    decisions = None; object_result = None; stage = 'selection'; code = 'selection_unresolved'; refine = set()
    selection_item = (dict(item,saved_reviews_only=True)
        if str(cut['card']) in item.get('saved_selection_cards',[]) else item)
    tracking_evidence = []; tracking_uncertainty = []
    for round_index in range(policy['refinement_rounds'] + 1):
        object_result = None; object_verified = None; object_corrections_applied = False
        tracking_evidence = []; tracking_uncertainty = []
        measured, metadata, attachments = _measure(cut, paths, indices, directory, item,
                                                   source_identity=source_sha)
        answer = ST.review(track,_review,cut, selection_item, metadata, attachments, directory, headers, bool(round_index), timeline=timeline)
        requested = _refine_frames(answer, indices)
        if requested is None:
            code = 'refinement_contract_invalid'; reason = '대상 변경 구간이 실측 후보 번호와 다릅니다.'; break
        decisions = _decisions(answer, metadata, measured['content'],visual_subject=visual_subject)
        if decisions is None:
            if requested and round_index < policy['refinement_rounds']:
                indices = sorted(set(indices) | requested)
                continue
            code = answer.get('code') or 'selection_contract_invalid' if isinstance(answer,dict) else 'selection_contract_invalid'
            reason = ((answer.get('reason') or '') + ' ' if isinstance(answer,dict) else '') + '모호하거나 누락된 선택입니다. 현재 보이는 화자를 임의의 얼굴로 대체하지 않습니다.'
            break
        track, refine = _track(paths, indices, decisions, cuts, pts, cut, policy, content=measured['content'])
        import subject_tracking_evidence as TE
        import sys
        refine.update(TE.relation_frames(answer,indices))
        tracking_uncertainty = TE.classify(indices,decisions,cuts,refine,answer)
        candidates = TE.static_candidates(sys.modules[__name__],paths,tracking_uncertainty)
        candidates = [r for r in candidates if not (set(range(r['left'],r['right']+1)) & (requested-set(indices)))]
        if candidates and all(decisions[r['left_sample']]['kind']=='object' and
                              decisions[r['right_sample']]['kind']=='object' for r in candidates):
            # Independent object verification is still mandatory before any
            # conservative static region becomes accepted geometry.
            object_result = ST.review(track,_object_review,item,cut,paths,indices,decisions,measured['content'],directory,headers)
            object_verified = isinstance(object_result,dict) and object_result.get('status')=='accepted'
            if not object_verified:
                stage='object_review'; code=(object_result or {}).get('code') or 'object_review_unresolved'
                reason=(object_result or {}).get('reason') or '물체 영역 검수가 완료되지 않았습니다.'
                break
            if object_verified:
                if object_result.get('corrected_boxes'):
                    x,y,w,h = measured['content']
                    for sample,bbox in object_result['corrected_boxes'].items():
                        d = decisions[int(sample)]; d['bbox'] = bbox
                        d['box'] = [(bbox[0]-x)/w,(bbox[1]-y)/h,bbox[2]/w,bbox[3]/h]
                    object_corrections_applied = True
                    track,refine = _track(paths,indices,decisions,cuts,pts,cut,policy,content=measured['content'])
                track,refine,tracking_evidence = TE.resolve_static(sys.modules[__name__],track,refine,
                    decisions,candidates,objects_verified=True)
        for issue in tracking_uncertainty:
            remaining=sorted(set(issue.pop('frames')) & refine)
            issue['status']='unresolved' if remaining else 'resolved'
            issue['remaining_frames']=remaining
        # A temporal interval asks for real missing evidence. Explicit valid
        # decisions already cover these frame indices, even if the model repeats
        # the same interval on the dense pass.
        refine.update(requested - set(indices))
        if not refine and all(t['bbox'] is not None for t in track):
            stage = 'object_review'
            if object_result is None:
                object_result = ST.review(track,_object_review,item, cut, paths, indices, decisions, measured['content'], directory, headers)
            object_verified = None if object_result is None else isinstance(object_result,dict) and object_result.get('status')=='accepted'
            if object_verified is False:
                code = object_result.get('code') or 'object_review_unresolved'
                reason = object_result.get('reason') or '물체 좌표에 대한 별도 자르기 검증을 완료하지 못했습니다.'; break
            if object_result and object_result.get('corrected_boxes') and not object_corrections_applied:
                x,y,w,h = measured['content']
                for sample,bbox in object_result['corrected_boxes'].items():
                    d = decisions[int(sample)]; d['bbox'] = bbox
                    d['box'] = [(bbox[0]-x)/w,(bbox[1]-y)/h,bbox[2]/w,bbox[3]/h]
                track,refine = _track(paths,indices,decisions,cuts,pts,cut,policy,content=measured['content'])
                if refine or any(t['bbox'] is None for t in track):
                    stage='tracking';code='corrected_tracking_incomplete'
                    reason='교정한 물체 상자의 전체 움직임을 확인하지 못했습니다. 교정 검사는 자동 반복하지 않습니다.';break
            final = decisions; break
        if round_index == policy['refinement_rounds']:
            stage='tracking';code='tracking_incomplete';reason = '한 번 더 확인한 뒤에도 선택 또는 움직임이 불확실합니다.'; break
        indices = sorted(set(indices) | refine)
    scene = dict(status='ok', start=float(cut['start']), fps=float(cut['fps']), nframes=len(paths),
                 cuts=cuts, source_identity=source_sha,
                 **({'frame_clock':cut['frame_clock']} if 'frame_clock' in cut else {}))
    output = dict(measured, focus_key=cut['focus_key'], focus_status='accepted' if final else 'unresolved',
                  source_identity=source_sha, scene_evidence=scene,
                  selection_runtime=dict(root=item['framevision'], algorithm=ALGORITHM_VERSION,
                      identity=hashlib.sha256(json.dumps(recipe['detector'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()))
    if source_digest(cut['src']) != source_sha:
        raise R.StepError('피사체 측정 중 원본 바이트가 바뀌었습니다. 기존 결과를 사용하지 않습니다.')
    if final:
        kinds = {d['kind'] for d in final}; kind = next(iter(kinds)) if len(kinds) == 1 else 'group'
        boxes = [t['bbox'] for t in track]
        import statistics
        bbox = [statistics.median(b[k] for b in boxes) for k in range(4)]
        evidence = dict(decisions=final, samples=metadata, engine=('visual-subject-and-measured-candidates' if visual_subject
                        else 'audio-video-and-measured-candidates' if cut.get('kind') != 'image' else 'image-and-measured-candidates'),
                        refinement_rounds=round_index, identity_verified=False)
        if hasattr(paths,'local_measurement'):
            evidence['local_measurement']=paths.local_measurement()
        if tracking_evidence:
            evidence['tracking_evidence'] = tracking_evidence
        if tracking_uncertainty:
            evidence['tracking_uncertainty'] = tracking_uncertainty
        if visual_subject:
            evidence['review_scope'] = 'visual_subject_v1'
        if object_verified is True:
            evidence['object_verified'] = True
            evidence['object_review'] = object_result
        output['framing_subject'] = dict(bbox=bbox, track=track, origin=float(cut['start']), complete=True,
                                         kind=kind, selection_evidence=evidence)
        x, y, w, h = output['content']
        output.update(by='face' if kind == 'face' else 'subject',
                      face=[bbox[0]-x, bbox[1]-y, bbox[2], bbox[3]] if kind == 'face' else None,
                      face_samples=[[b[0]-x, b[1]-y, b[2], b[3]] for b in boxes] if kind == 'face' else [],
                      face_sample_times=[t['t'] for t in track] if kind == 'face' else [],
                      subject=[(bbox[0]+bbox[2]/2-x)/w, (bbox[1]+bbox[3]/2-y)/h],
                      subject_detected=kind != 'scene', subject_sample_coverage=1, tracking_capture_coverage=1,
                      track_origin=float(cut['start']), _recipe=key)
        R._photo_write_state(str(cache), output)
    else:
        observed = decisions if decisions is not None else ((answer.get('decisions') or []) if isinstance(answer,dict) else [])
        evidence = {'stage':stage,'code':code,'reason':reason,'decisions':observed,
                    'samples':metadata,'track_gaps':sorted(refine | {t['frame_index'] for t in track if t['bbox'] is None}),
                    'refinement_rounds':round_index,'automatic_retry':False}
        if hasattr(paths,'local_measurement'):
            evidence['local_measurement']=paths.local_measurement()
        if tracking_evidence:
            evidence['tracking_evidence'] = tracking_evidence
        if tracking_uncertainty:
            evidence['tracking_uncertainty'] = tracking_uncertainty
        if visual_subject:
            evidence['review_scope'] = 'visual_subject_v1'
        if object_result is not None:
            evidence['object_review'] = object_result
        if isinstance(answer,dict):
            evidence['review_verdict'] = answer.get('verdict')
            evidence['refine_intervals'] = answer.get('refine_intervals') or []
        output.update(by='unresolved', face=None, face_samples=[], subject_detected=False,
                      framing_subject=dict(bbox=None, track=[], origin=float(cut['start']), complete=False,
                                           kind='unresolved', selection_evidence=evidence),
                      focus_recovery={'status':'needs_evidence','stage':stage,'code':code,'automatic_retry':False})
        R._photo_write_state(str(directory/'unresolved.json'),output)
    return output


def _accepted_motion(row, cut, source_identity, directory):
    """Pixel failures do not revoke an independently accepted semantic row."""
    try:
        _enrich_motion(row, cut, source_identity, directory)
        row.pop('source_motion_error', None)
    except (R.StepError, RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
        row.pop('motion', None)
        row.pop('source_motion', None)
        row['source_motion_error'] = str(error)
    # The enclosing source guard still rejects replaced/mutated media.
    return row


def _enrich_motion(row, cut, source_identity, directory):
    """Add missing source pixels to a valid semantic receipt without re-review."""
    if cut.get('kind') != 'video' or len(cut.get('samples') or []) < 2:
        return row
    import source_motion
    expected = source_motion.recipe(cut, row['content'], source_identity)
    prior = row.get('source_motion')
    if (isinstance(prior, dict) and {k:prior.get(k) for k in expected} == expected
            and _number(prior.get('value')) and prior['value'] >= 0
            and _number(row.get('motion')) and row.get('motion') == prior['value']):
        M.event('subject_source_motion', 'reused')
        return row
    with M.span('subject_source_motion', publish=True):
        receipt = source_motion.measure(cut, row['content'], source_identity, directory)
    row.update(motion=receipt['value'], source_motion=receipt)
    return row


def measure_source_motions(item):
    """Metric-only recovery for already selected sources; no detector or review."""
    import source_motion
    result = {}
    with R._ArgvInputDigests() as digests:
        for cut in item['cuts']:
            source_identity = digests.digest(cut['src'])
            if source_identity != cut['source_identity']:
                raise R.StepError('움직임을 잴 원본이 선택한 파일과 다릅니다. 바뀐 원본의 선택부터 확인하세요.')
            request = source_motion.recipe(cut, cut['content'], source_identity)
            # Reuse the independently bound scalar receipt in the accepted directory.
            key = cut.get('selection_recipe_key')
            folder = Path(item['out_dir']) / (key if isinstance(key, str) and re.fullmatch(r'[0-9a-f]{64}', key)
                                              else source_motion._digest(request))
            with M.unit('cut_'+str(cut['card'])), M.span('subject_source_motion', publish=True):
                result[str(cut['card'])] = source_motion.measure(cut, cut['content'], source_identity, folder)
        digests.check()
    return result


def select_subjects(item, headers=None):
    """Bounded independent cuts; one failure never invents another cut's result."""
    _policy(item)
    if 'saved_reviews_only' in item and type(item['saved_reviews_only']) is not bool:
        raise R.StepError('saved_reviews_only는 불리언이어야 합니다.')
    saved_cards = item.get('saved_selection_cards',[])
    if not isinstance(saved_cards,list) or any(not isinstance(card,str) for card in saved_cards):
        raise R.StepError('saved_selection_cards는 컷 번호 문자열 목록이어야 합니다.')
    item = dict(R.review_execution_settings(item),
                _detector_identity=_detector_identity(item['framevision']),
                _timeline_locks={},_timeline_lock_guard=threading.Lock(),
                _frame_locks={},_frame_lock_guard=threading.Lock())
    cuts = item['cuts']
    if len({str(c['card']) for c in cuts}) != len(cuts):
        raise R.StepError('피사체 선택 컷 번호가 중복되었습니다.')
    # 사람이 «고쳤으니 다시» 를 알린 컷(local_focus 가 준다) — 그 컷의 작업 동안만 끝나지 않은 검수 영수증을 한 번 놓아 준다
    #   (volcano_run.review_retry_scope · release_unfinished_review: 질문을 실제로 다시 묻는 그 자리에서 판정한다).
    retry_cards = item.get('retry_cards') or []
    if not isinstance(retry_cards, list) or any(not isinstance(card, str) for card in retry_cards):
        raise R.StepError('retry_cards는 컷 번호 문자열 목록이어야 합니다.')
    retry_cards = frozenset(retry_cards)
    retry_registry = R.review_retry_registry() if retry_cards else None
    # 검수 엔진이 결과 없이 끝난 대기(client_review 의 engine_failed)를 «사람 답 대기» 가 아니라 실행 실패 행으로 낸다 —
    #   부르는 쪽이 opt-in(local_focus): 그 행은 막힌 컷의 «다시» 로 풀린다. 다른 부르는 쪽의 기존 흐름은 그대로다.
    engine_rows = item.get('engine_failure_rows') is True
    stages = None
    def failure(cut, code, reason, error=None):
        return {'focus_key': cut.get('focus_key'), 'focus_status': 'unresolved',
                **({'review_budget_blocked':error.review_budget_blocked} if getattr(error,'review_budget_blocked',None) else {}),
                **({} if item.get('saved_reviews_only') is True else {'_error':reason}),
                'focus_recovery':{'status':'needs_evidence','stage':'execution','code':code,'automatic_retry':False},
                'framing_subject': {'complete': False, 'track': [],
                'kind': 'unresolved', 'selection_evidence': {'stage':'execution','code':code,'reason':reason,'automatic_retry':False}}}
    def work(cut):
        try:
            with M.unit('cut_'+str(cut['card'])), M.span('subject_selection', publish=True), \
                    R.review_retry_scope(str(cut['card']) in retry_cards, retry_registry):
                return str(cut['card']), (stages.run(_one,cut,item,headers,input_digests) if stages else _one(cut,item,headers,input_digests))
        except R.ClientReviewPending as pending:
            if engine_rows and getattr(pending, 'engine_failed', False):
                return str(cut['card']), failure(cut, getattr(pending, 'engine_code', None) or 'client_review_no_result',
                                                 getattr(pending, 'engine_reason', '') or str(pending))
            return str(cut['card']), {'focus_key':cut.get('focus_key'),'focus_status':'pending',
                'review_requests':[pending.request],
                'framing_subject':{'complete':False,'track':[],'kind':'unresolved',
                    'selection_evidence':{'stage':'client_review','code':pending.code,'reason':str(pending),'automatic_retry':False}}}
        except (R.StepError, RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
            code = 'provider_refused' if isinstance(error,R.ProviderRefusalError) else _http_failure_code(getattr(error,'code','selection_execution_failed'))
            return str(cut['card']), failure(cut, code, str(error), error)
    width = max(1, min(int(item.get('parallel') or 1), len(cuts) or 1))
    with R.review_context(policy=item.get('review_policy'),client=item.get('review_client'),
                          replies=item.get('focus_review_replies'),budget=item.get('_review_budget')):
        with R._ArgvInputDigests() as input_digests:
            selected = R.resolve_review_client(item.get('review_client'))
            native_agy = (R.resolve_review_policy(item.get('review_policy'))['provider']=='client'
                          and selected['provider']=='agy')
            if native_agy:
                import agy_transport_client as AGY
                stages=ST.Stages(width,check_running=R.check_review_running)
                # ★부르는 쪽이 이 일감의 구독 AGY 동시 수를 정할 수 있다(agy_parallel · 2026-10-08 쇼핑 가로 원본 초점이
                #   컷마다 AGY 를 한꺼번에 약 10개 띄웠다 → 4). 없으면 예전대로 전송 표의 기계 전체 상한(maxParallel)까지.
                continuations=min(AGY.max_parallel(),len(cuts) or 1,
                                  max(1,int(item.get('agy_parallel') or AGY.max_parallel())))
                with ThreadPoolExecutor(max_workers=continuations) as pool:
                    result=dict(pool.map(R.review_context_worker(work),cuts))
            else:
                with ThreadPoolExecutor(max_workers=width) as pool:
                    result = dict(pool.map(R.review_context_worker(work), cuts))
            input_digests.check()
            return result
