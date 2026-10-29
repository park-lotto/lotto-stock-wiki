"""An explicit output clock sampled from real source PTS, with no EOF padding.

FFmpeg's accurate input seek discards preroll. Keep it through resampling so
an in-between-frame start can sample the picture actually covering that time.
Official option semantics: https://ffmpeg.org/ffmpeg.html#Main-options
FPS start_time is the output PTS origin: https://ffmpeg.org/ffmpeg-filters.html#fps
No tpad, synthetic final picture, provider operation or changed frame count.
"""
import math
CONTRACT='source-pts-v1'

def _number(value):
    return type(value) in (int,float) and math.isfinite(value)

def validate(cut,timeline):
    if cut.get('frame_clock')!=CONTRACT:raise ValueError('unknown source frame clock')
    start,fps,duration=(cut.get(k) for k in ('start','fps','duration'))
    if not all(_number(v) for v in (start,fps,duration)) or start<0 or fps<=0 or duration<=0:
        raise ValueError('invalid source frame clock')
    frames=round(duration*fps)
    if frames<1:raise ValueError('empty source frame clock')
    if not isinstance(timeline,dict) or not all(_number(timeline.get(k)) for k in ('origin','start','end')):
        raise ValueError('source frame clock requires measured video boundaries')
    if start<max(0,timeline['start']) or start+(frames-1)/fps>=timeline['end']:
        raise ValueError('requested sample lies outside real video interval')
    return frames

def input_options(cut,timeline):
    validate(cut,timeline)
    return ['-copyts','-ss',str(cut['start']),'-noaccurate_seek']

def grid(cut,timeline):
    frames=validate(cut,timeline)
    anchor=cut.get('clock_start',cut['start'])
    if not _number(anchor) or anchor<0:raise ValueError('invalid accepted clock origin')
    offset=(cut['start']-anchor)*cut['fps'];first=round(offset)
    if first<0 or abs(offset-first)>1e-6:raise ValueError('render window is outside accepted frame grid')
    at=anchor+timeline['origin']
    # Keep the exact original source time-base rounding even for subwindows.
    # Trim integer output PTS after resampling; changing fps start_time would
    # independently round its input offset and shift approved pictures.
    grid=f"setpts=PTS-round({at:.12g}/TB),fps={cut['fps']:.12g},trim=start_pts={first}:end_pts={first+frames},setpts=PTS-STARTPTS"
    return grid

def choose(R,directory,binding,requested=None):
    """Choose only before a question exists; never move a paid/unknown question.

    The marker is separate from every existing receipt. It is published before
    the first decode/question, and cannot be switched by a later server choice.
    """
    import json
    from pathlib import Path
    directory=Path(directory);marker=directory/'frame-clock-choice.json'
    if requested not in (None,CONTRACT):raise R.StepError('unknown requested frame clock')
    if requested is None and not marker.exists():return None
    with R.review_receipt_lock(str(marker)):
        if marker.exists():
            try:saved=json.loads(marker.read_text(encoding='utf-8'))
            except (OSError,ValueError) as exc:raise R.StepError('frame clock receipt unreadable; preserve existing reviews') from exc
            if (not isinstance(saved,dict) or set(saved)!={'version','binding','contract'}
                    or type(saved['version']) is not int or saved['version']!=1
                    or saved['binding']!=binding or saved['contract'] not in ('legacy',CONTRACT)):
                raise R.StepError('frame clock receipt differs; preserve existing reviews')
            return None if saved['contract']=='legacy' else saved['contract']
        ignored={marker,Path(str(marker)+'.lock'),directory/'clock-execution.lock'}
        existing=any(p not in ignored for p in directory.iterdir())
        selected='legacy' if existing else CONTRACT
        R._photo_write_state(str(marker),dict(version=1,binding=binding,contract=selected))
        return None if selected=='legacy' else selected


def select(R,directory,binding,requested,execution):
    from contextlib import ExitStack
    with ExitStack() as held:
        return _select(R,directory,binding,requested,execution,held)


def _select(R,directory,binding,requested,execution,held):
    """Recover extraction-only failures, keeping old bytes and legacy locks.

    Existing runners already acquire frame-cache-ref/frame-evidence locks before
    publishing a successful extraction. Hold those same locks through this cut,
    not merely a new mutex which old versions do not know about. No global lock.
    """
    import hashlib,json,re
    from pathlib import Path
    directory=Path(directory);proof=directory/'pre-review-clock-proof.json'
    def sha(path):
        value=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
        return value.hexdigest()
    def fail():raise R.StepError('프레임 시간축 복구 증거가 다릅니다. 기존 원본·검수 기록을 보존합니다.')
    selected=choose(R,directory,binding,requested)
    if not proof.exists() and (selected is not None or requested!=CONTRACT):return selected,directory
    held.enter_context(R.review_receipt_lock(str(directory/'frame-cache-ref.json')))
    held.enter_context(R.review_receipt_lock(str(directory/'frame-evidence.json')))
    if proof.exists():
        try:
            saved=json.loads(proof.read_text(encoding='utf-8'))
            if (set(saved)!={'version','binding','contract','artifacts','target'} or saved['version']!=1
                    or type(saved['version']) is not int or saved['binding']!=binding or saved['contract']!=CONTRACT
                    or saved['target']!='pre-review-clock-v1' or not isinstance(saved['artifacts'],dict)
                    or not saved['artifacts'] or 'frame-clock-choice.json' not in saved['artifacts']):fail()
            for name,digest in saved['artifacts'].items():
                if (not isinstance(name,str) or Path(name).name!=name
                        or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest)
                        or not (name in ('frame-clock-choice.json','frame-cache-ref.json','frame-error.log','frame-error.json')
                                or re.fullmatch(r'frame_\d{6,}\.png',name))):fail()
                path=directory/name
                if path.is_symlink() or not path.is_file() or sha(path)!=digest:fail()
        except (OSError,ValueError,TypeError) as exc:
            raise R.StepError('프레임 시간축 복구 증거를 읽지 못했습니다. 기존 원본·검수 기록을 보존합니다.') from exc
        allowed=set(saved['artifacts'])|{'pre-review-clock-proof.json','pre-review-clock-v1',
            'frame-clock-choice.json.lock','clock-execution.lock','frame-cache-ref.json.lock','frame-evidence.json.lock'}
        if any(p.name not in allowed or p.is_symlink() for p in directory.iterdir()):fail()
        if (directory/'frame-evidence.json').exists():fail()
        ref=directory/'frame-cache-ref.json'
        if ref.is_file():
            old=json.loads(ref.read_text(encoding='utf-8'))
            legacy=directory.parent/'.frame-cache'/old['recipe_sha256']
            if legacy.is_symlink() or legacy.parent.is_symlink() or not legacy.is_dir():fail()
            held.enter_context(R.review_receipt_lock(str(legacy/'frame-evidence.json')))
            if any(p.name!='frame-evidence.json.lock' or p.is_symlink() or not p.is_file() for p in legacy.iterdir()):fail()
            for sibling in directory.parent.iterdir():
                if sibling==directory or not sibling.is_dir() or sibling.is_symlink():continue
                linked=sibling/'frame-cache-ref.json'
                if not linked.is_file():continue
                try:other=json.loads(linked.read_text(encoding='utf-8'))
                except (OSError,ValueError) as exc:
                    raise R.StepError('연결된 프레임 복구 기록을 읽지 못했습니다. 기존 원본·검수 기록을 보존합니다.') from exc
                if isinstance(other,dict) and other.get('recipe_sha256')==old['recipe_sha256']:
                    permitted={'frame-cache-ref.json','frame-cache-ref.json.lock','frame-clock-choice.json',
                               'frame-clock-choice.json.lock','clock-execution.lock'}
                    if any(p.name not in permitted for p in sibling.iterdir()):fail()
        target=directory/saved['target']
        if target.is_symlink():fail()
        target.mkdir(exist_ok=True)
        execution.enter_context(held.pop_all())
        return CONTRACT,target
    # Same lock names/order as the historical reader. Nonwaiting lock failure
    # propagates, so an active decoder never becomes a recovery candidate.
    marker=directory/'frame-clock-choice.json'
    ignored={'frame-clock-choice.json','frame-clock-choice.json.lock','clock-execution.lock',
             'frame-cache-ref.json.lock','frame-evidence.json.lock'}
    artifacts={};seen=False
    for path in directory.iterdir():
        if path.is_symlink():return None,directory
        if path.name in ignored:
            if not path.is_file() or (path.name.endswith('.lock') and path.stat().st_size):return None,directory
            continue
        if not path.is_file():return None,directory
        if path.name=='frame-cache-ref.json':
            try:
                ref=json.loads(path.read_text(encoding='utf-8'))
                if (set(ref)!={'version','recipe_sha256'} or ref['version']!=1
                        or not re.fullmatch('[0-9a-f]{64}',ref['recipe_sha256'])):return None,directory
                target=directory.parent/'.frame-cache'/ref['recipe_sha256']
                if target.is_symlink() or target.parent.is_symlink() or not target.is_dir():return None,directory
                for sibling in directory.parent.iterdir():
                    if sibling==directory or not sibling.is_dir() or sibling.is_symlink():continue
                    linked=sibling/'frame-cache-ref.json'
                    if not linked.is_file():continue
                    try:other=json.loads(linked.read_text(encoding='utf-8'))
                    except (OSError,ValueError):return None,directory
                    if isinstance(other,dict) and other.get('recipe_sha256')==ref['recipe_sha256']:
                        allowed={'frame-cache-ref.json','frame-cache-ref.json.lock',
                                 'frame-clock-choice.json','frame-clock-choice.json.lock','clock-execution.lock'}
                        if any(p.name not in allowed for p in sibling.iterdir()):return None,directory
                if target.exists():
                    held.enter_context(R.review_receipt_lock(str(target/'frame-evidence.json')))
                    # No completed receipt, partial published sample or unknown
                    # evidence may have escaped extraction in this old target.
                    if any(p.name!='frame-evidence.json.lock' or p.is_symlink() or not p.is_file()
                           for p in target.iterdir()):return None,directory
            except (OSError,ValueError,TypeError):return None,directory
        elif path.name in ('frame-error.log','frame-error.json'):
            if path.name.endswith('.json'):
                try:
                    error=json.loads(path.read_text(encoding='utf-8'))
                    if (set(error)!={'expected_images','record_counts','first_wrong_indices','missing_indices'}
                            or type(error['expected_images']) is not int or error['expected_images']<1
                            or set(error['record_counts'])!={'source','fps','all','cut'}
                            or any(type(x) is not int or x<0 for x in error['record_counts'].values())
                            or not isinstance(error['first_wrong_indices'],list)
                            or not isinstance(error['missing_indices'],list)):return None,directory
                except (OSError,ValueError,TypeError):return None,directory
        elif re.fullmatch(r'frame_\d{6,}\.png',path.name):
            try:
                from PIL import Image
                with Image.open(path) as image:
                    if image.format!='PNG':return None,directory
                    image.verify()
            except (OSError,ValueError):return None,directory
        else:return None,directory
        seen=True;artifacts[path.name]=sha(path)
    if not seen or not ({'frame-cache-ref.json','frame-error.json'} & artifacts.keys()):return None,directory
    # Pointer-only means extraction never published. Local PNGs require the
    # exact pre-review count-failure record, not a guessed arbitrary file set.
    if any(name.startswith('frame_') for name in artifacts) and 'frame-error.json' not in artifacts:return None,directory
    if marker.is_file():artifacts[marker.name]=sha(marker)
    saved=dict(version=1,binding=binding,contract=CONTRACT,artifacts=artifacts,target='pre-review-clock-v1')
    R._photo_write_state(str(proof),saved)
    target=directory/saved['target'];target.mkdir(exist_ok=True)
    execution.enter_context(held.pop_all())
    return CONTRACT,target
