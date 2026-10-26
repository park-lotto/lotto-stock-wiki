"""Source-bound sampled PNG evidence and on-demand dense pixel decoding.

Only selected review PNGs are durable. Dense optical flow receives the unchanged
FFmpeg PNG byte stream; a scene-only track never starts that stream.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import os
import shutil
from pathlib import Path
import struct
import subprocess
import tempfile
import threading


def sampled_frames(F, cut, directory, policy, *, source_digest, timeline, before_decode):
    if cut.get('kind') != 'video':
        return F._frames(cut, directory, policy, source_digest=source_digest,
                         timeline=timeline, before_decode=before_decode)
    frames = SampledFrames(F, cut, directory, policy, source_digest, timeline)
    frames.initialize(before_decode)
    paths = ([frames[i] for i in range(len(frames))]
             if 'storage' not in frames.saved and all(frames[i].is_file() for i in range(len(frames))) else frames)
    return paths, frames.saved['cuts'], frames.saved['pts']


class SampledFrames:
    def __init__(self, F, cut, directory, policy, digest, timeline):
        self.F, self.cut, self.directory, self.policy = F, cut, directory, policy
        self.digest, self.timeline = digest, timeline
        self.source_sha = digest(cut['src'])
        self.recipe = F._frame_recipe(cut, policy, self.source_sha)
        self.count = round(float(cut['duration']) * float(cut['fps']))
        self.manifest = directory / 'frame-evidence.json'
        self.saved = None
        self.pipe = None
        self.observed_hashes = {}

    def __len__(self):
        return self.count

    def __eq__(self, other):
        if not isinstance(other, SampledFrames):
            return NotImplemented
        return (self.directory, self.count, self.recipe) == (other.directory, other.count, other.recipe)

    def __getitem__(self, index):
        if type(index) is not int or not 0 <= index < self.count:
            raise IndexError(index)
        return self.directory / f'frame_{index:06d}.png'

    def fail(self, message):
        raise self.F.R.StepError(message + ' 기존 검수·원본 프레임은 보존합니다.')

    def check_source(self):
        if self.digest(self.cut['src']) != self.source_sha:
            self.fail('프레임 측정 중 원본 바이트가 바뀌었습니다.')
        if self.F._frame_recipe(self.cut, self.policy, self.source_sha) != self.recipe:
            self.fail('프레임 디코더 또는 시간 조건이 바뀌었습니다.')

    def hashes(self, saved=None):
        saved = self.saved if saved is None else saved
        if saved.get('storage') == 'sampled-png-v1':
            return {int(k): v for k, v in saved['samples'].items()}
        return dict(enumerate(saved['sha256']))

    def validate(self, saved, *, files=True):
        if not isinstance(saved, dict) or not self.F._frame_recipe_matches(saved.get('recipe'),self.recipe,self.cut,self.policy,self.directory):
            self.fail('저장된 프레임 원본·시간 조건이 다릅니다.')
        pts, cuts = saved.get('pts'), saved.get('cuts')
        if (not isinstance(pts, list) or len(pts) != self.count
                or any(p is not None and not self.F._number(p) for p in pts)
                or not isinstance(cuts, list) or any(type(i) is not int or not 0 < i < self.count for i in cuts)
                or cuts != sorted(set(cuts))):
            self.fail('저장된 프레임 시간축이 잘못되었습니다.')
        if saved.get('storage') == 'sampled-png-v1':
            samples = saved.get('samples')
            if (saved.get('nframes') != self.count or not isinstance(samples, dict)
                    or any(not isinstance(k,str) or not k.isascii() or not k.isdigit()
                           or str(int(k)) != k or not 0 <= int(k) < self.count for k in samples)):
                self.fail('저장된 표본 번호가 잘못되었습니다.')
        elif ('storage' in saved or not isinstance(saved.get('sha256'), list)
              or len(saved['sha256']) != self.count):
            self.fail('저장된 프레임 영수증 형식을 확인하지 못했습니다.')
        hashes = self.hashes(saved)
        if any(not isinstance(v,str) or len(v) != 64 or any(c not in '0123456789abcdef' for c in v)
               for v in hashes.values()):
            self.fail('저장된 프레임 SHA가 잘못되었습니다.')
        self.F._check_source_pts(pts, self.cut, self.timeline)
        if not files:
            return
        for index, expected in hashes.items():
            path = self[index]
            if path.exists() and self.F._sha(path) != expected:
                self.fail('기존 검수 프레임 바이트가 바뀌었습니다.')
        if self.cut.get('video_timing') is not None:
            timing = self.directory / 'video-timing.json'
            if not timing.is_file() or self.F._sha(timing) != saved.get('timing_sha256'):
                self.fail('기존 영상 시간축 영수증이 없거나 바뀌었습니다.')

        # Missing old samples may be recovered only under the old exact recipe;
        # do not mint a content proof until all recorded pixels are present.
        if all(self[index].is_file() for index in hashes):
            self.F._record_frame_decoder(saved,self.recipe,self.cut,self.policy,self.directory,source_digest=self.digest)

    def recover(self):
        journal = self.directory / 'sample-transaction.json'
        if not journal.exists():
            return
        try:
            record = json.loads(journal.read_text(encoding='utf-8'))
            name = record['stage']
            if not isinstance(name,str) or Path(name).name != name or not name.startswith('.sample-evidence-'):
                raise ValueError('invalid stage')
            stage = self.directory.parent / name
            saved = record['saved']
            entries = record['incoming']
            if not isinstance(entries,dict) or any(not self.F.re.fullmatch(r'frame_\d{6,}\.png|video-timing\.json', k) for k in entries):
                raise ValueError('invalid incoming')
            self.validate(saved, files=False)
            expected_hashes = self.hashes(saved)
            for name, sha in entries.items():
                expected = (saved.get('timing_sha256') if name == 'video-timing.json' else
                            expected_hashes.get(int(name[6:-4])))
                if sha != expected:
                    raise ValueError('incoming bytes are not bound to receipt')
            current_sha = self.F._sha(self.manifest) if self.manifest.exists() else None
            if current_sha != record['previous_manifest_sha']:
                current = json.loads(self.manifest.read_text(encoding='utf-8')) if self.manifest.exists() else None
                if current != saved:
                    raise ValueError('prior receipt changed during interrupted publication')
            self.check_source()
            for name, sha in entries.items():
                target = self.directory / name
                if target.exists():
                    if self.F._sha(target) != sha:
                        raise ValueError('existing evidence differs')
                else:
                    path = stage / name
                    if self.F._sha(path) != sha:
                        raise ValueError('staged evidence differs')
                    os.replace(path, target)
            # All new bytes are present before publishing their binding.
            self.validate(saved)
            self.check_source()
            existing = json.loads(self.manifest.read_text(encoding='utf-8')) if self.manifest.exists() else None
            if existing != saved:
                self.F.R._photo_write_state(str(self.manifest), saved)
            os.replace(journal, stage / 'committed.json')
        except Exception as exc:
            self.fail('표본 프레임 게시 복구를 완료하지 못했습니다: ' + str(exc))

    def adopt_declared_timing(self, saved):
        """Prove legacy trim pixels before binding an explicit canonical grid.

        Tail hold is not a spelling difference: decode locally and compare every
        recorded sample plus the complete PTS/scene grid. Never ask a provider.
        """
        if (not isinstance(saved, dict) or self.cut.get('video_timing') is None
                or self.cut.get('seek_mode') != 'trim'
                or not isinstance(saved.get('recipe'), dict)
                or saved['recipe'].get('cut', {}).get('video_timing') is not None):
            return
        legacy_cut = dict(self.cut)
        legacy_cut.pop('video_timing')
        legacy_recipe = self.F._frame_recipe(legacy_cut, self.policy, self.source_sha)
        if not self.F._frame_recipe_matches(saved['recipe'], legacy_recipe,
                                            legacy_cut, self.policy, self.directory):
            return
        # Validate the old binding and all retained pixels before any migration.
        old_cut, old_recipe = self.cut, self.recipe
        try:
            self.cut, self.recipe = legacy_cut, legacy_recipe
            self.validate(saved)
        finally:
            self.cut, self.recipe = old_cut, old_recipe
        hashes = self.hashes(saved)
        if not hashes:
            self.fail('기존 시간축에 연결할 검증된 표본이 없습니다.')
        with self.F._frame_storage_reservation(self.cut, self.directory, len(hashes)):
            stage = Path(tempfile.mkdtemp(prefix='.sample-evidence-', dir=self.directory.parent))
            decode = stage / 'decode' / self.directory.name
            decode.mkdir(parents=True)
            indices = sorted(hashes)
            paths, cuts, pts = self.F._decode_frames(self.cut, decode, self.policy,
                                                    wanted_indices=indices, timeline=self.timeline)
            if (len(paths) != len(indices) or pts != saved['pts'] or cuts != saved['cuts']
                    or any(self.F._sha(p) != hashes[i] for i, p in zip(indices, paths))):
                self.fail('명시된 영상 시간축이 기존 검수 표본·시간축과 다릅니다.')
            self.check_source()
            timing = decode / 'video-timing.json'
            timing_sha = self.F._sha(timing)
            target = self.directory / timing.name
            if target.exists() and self.F._sha(target) != timing_sha:
                self.fail('기존 영상 시간축 영수증과 새 측정이 다릅니다.')
            adopted = dict(saved, recipe=self.recipe, timing_sha256=timing_sha)
            backup = stage / 'previous-frame-evidence.json'
            shutil.copy2(self.manifest, backup)
            for evidence in (backup, timing):
                with evidence.open('r+b') as stream:
                    os.fsync(stream.fileno())
            os.replace(timing, stage / timing.name)
            self.F.R._photo_write_state(str(self.directory / 'sample-transaction.json'),
                dict(stage=stage.name, saved=adopted, incoming={timing.name:timing_sha},
                     previous_manifest_sha=self.F._sha(self.manifest)))
            self.recover()
            self.saved = adopted

    def initialize(self, before_decode):
        self.F._video_timing(self.cut)
        with self.F.R.review_receipt_lock(str(self.manifest)):
            self.F._recover_frame_transaction(self.directory)
            self.recover()
            if self.manifest.exists():
                try:
                    self.saved = json.loads(self.manifest.read_text(encoding='utf-8'))
                except (ValueError, OSError):
                    self.fail('기존 프레임 영수증을 읽지 못했습니다.')
                self.adopt_declared_timing(self.saved)
                self.validate(self.saved)
            else:
                if before_decode:
                    before_decode()
                if any(self.directory.glob('frame_*.png')):
                    self.fail('원래 영수증 없는 부분 프레임을 새 검수에 연결할 수 없습니다.')
            self.check_source()
        step = max(1, round(float(self.policy['sample_interval']) * float(self.cut['fps'])))
        indices = sorted(set(range(0,self.count,step)) | {self.count-1})
        self.prepare(indices)
        self.prepare(sorted({i for c in self.saved['cuts'] for i in (c-1,c)}))

    def prepare(self, indices):
        if any(type(i) is not int or not 0 <= i < self.count for i in indices):
            self.fail('추가 표본 번호가 영상 격자와 다릅니다.')
        if not indices:
            return
        F = self.F
        with F.R.review_receipt_lock(str(self.manifest)):
            self.recover()
            if self.manifest.exists():
                self.saved = json.loads(self.manifest.read_text(encoding='utf-8'))
                self.validate(self.saved)
            self.check_source()
            known = self.hashes() if self.saved is not None else {}
            missing = sorted(set(i for i in indices if i not in known or not self[i].is_file()))
            if not missing:
                return
            with F._frame_storage_reservation(self.cut, self.directory, len(missing)):
                stage = Path(tempfile.mkdtemp(prefix='.sample-evidence-',dir=self.directory.parent))
                decode_dir = stage / 'decode' / self.directory.name; decode_dir.mkdir(parents=True)
                paths, cuts, pts = F._decode_frames(self.cut, decode_dir, self.policy,
                                                   wanted_indices=missing, timeline=self.timeline)
                self.check_source()
                new_hashes = {index:F._sha(path) for index,path in zip(missing,paths)}
                if len(paths) != len(missing):
                    self.fail('추가 표본 개수가 맞지 않습니다.')
                if self.saved is not None:
                    if (self.saved['pts'] != pts
                            or (self.saved.get('storage') == 'sampled-png-v1' and self.saved['cuts'] != cuts)
                            or any(i in known and known[i] != sha for i,sha in new_hashes.items())):
                        self.fail('추가 표본이 원래 바이트·시간축과 다릅니다.')
                    # Legacy cuts intentionally remain authoritative for an existing question.
                    saved = dict(self.saved)
                else:
                    saved = dict(storage='sampled-png-v1', nframes=self.count, recipe=self.recipe,
                                 cuts=cuts, pts=pts, samples={}, scene_algorithm='native-grid-v3')
                if saved.get('storage') == 'sampled-png-v1':
                    saved['samples'] = dict(saved['samples'], **{str(i):sha for i,sha in new_hashes.items()})
                incoming = {}
                # Rename via a second folder: selected output numbering is packed,
                # while durable sample names retain their full timeline indices.
                publish = stage / 'publish'; publish.mkdir()
                for index,path in zip(missing,paths):
                    name = self[index].name
                    os.replace(path,publish/name)
                    incoming[name] = new_hashes[index]
                timing = decode_dir/'video-timing.json'
                if self.cut.get('video_timing') is not None:
                    timing_sha = F._sha(timing)
                    if self.saved is not None and self.saved.get('timing_sha256') != timing_sha:
                        self.fail('추가 표본의 시간축 영수증이 다릅니다.')
                    saved['timing_sha256'] = timing_sha
                    os.replace(timing,publish/timing.name)
                    incoming[timing.name] = timing_sha
                for path in publish.iterdir():
                    with path.open('r+b') as stream:
                        os.fsync(stream.fileno())
                    os.replace(path,stage/path.name)
                previous_sha = F._sha(self.manifest) if self.manifest.exists() else None
                if previous_sha is not None:
                    backup = stage/'previous-frame-evidence.json'
                    shutil.copy2(self.manifest, backup)
                    with backup.open('r+b') as stream:
                        os.fsync(stream.fileno())
                F.R._photo_write_state(str(self.directory/'sample-transaction.json'),
                                      dict(stage=stage.name,saved=saved,incoming=incoming,
                                           previous_manifest_sha=previous_sha))
                self.recover()
                self.saved = saved

    @contextmanager
    def tracking(self):
        self.check_source()
        try:
            yield
            self.check_source()
        finally:
            if self.pipe is not None:
                pipe, self.pipe = self.pipe, None
                pipe.close()

    def gray_at(self, index):
        from PIL import Image
        import numpy as np
        expected = self.hashes().get(index)
        if expected is not None and self[index].is_file():
            actual = self.F._sha(self[index])
            if actual != expected:
                self.fail('추적에 쓰는 기존 표본 바이트가 바뀌었습니다.')
            self.observed_hashes[index] = actual
            with Image.open(self[index]) as image:
                return np.asarray(image.convert('L'))
        with Image.open(io.BytesIO(self._stream_at(index))) as image:
            return np.asarray(image.convert('L'))

    def _stream_at(self, index):
        if self.pipe is None:
            args = self.F._decode_frames(self.cut, self.directory, self.policy,
                                         timeline=self.timeline, _command_only=True)
            self.pipe = PixelPipe(self, args[:-1]+['-c:v','png','-f','image2pipe','pipe:1'])
        return self.pipe.at(index)

    def png_sha_at(self, index):
        expected = self.hashes().get(index)
        if expected is not None and self[index].is_file():
            actual = self.F._sha(self[index])
            if actual != expected:
                self.fail('추적에 쓰는 기존 표본 바이트가 바뀌었습니다.')
            self.observed_hashes[index] = actual
        if index not in self.observed_hashes:
            self._stream_at(index)
        return self.observed_hashes[index]


class PixelPipe:
    def __init__(self, frames, command):
        self.frames = frames
        self.expected_hashes = frames.hashes()
        self.log = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        except BaseException:
            self.log.close()
            raise
        self.errors = None
        def drain():
            try:
                while True:
                    chunk = self.process.stderr.read(65536)
                    if not chunk:
                        break
                    self.log.write(chunk)
            except BaseException as error:
                self.errors = error
        self.reader = threading.Thread(target=drain,daemon=True)
        self.reader.start()
        self.index = -1
        self.raw = None

    def read(self, count):
        result = bytearray()
        while len(result) < count:
            part = self.process.stdout.read(count-len(result))
            if not part:
                self.frames.fail('추적 프레임 스트림이 중간에 끝났습니다.')
            result.extend(part)
        return result

    def at(self, index):
        if index < self.index:
            self.frames.fail('추적 프레임 순서가 거꾸로 되었습니다.')
        while self.index < index:
            raw = self.read(8)
            if raw != b'\x89PNG\r\n\x1a\n':
                self.frames.fail('추적 프레임 PNG 형식이 잘못되었습니다.')
            while True:
                header = self.read(8)
                size = int.from_bytes(header[:4],'big')
                # PNG specification limits chunk length to 2^31-1. Stream payload
                # in bounded reads rather than allocating from a supplied length.
                if size > 0x7fffffff:
                    self.frames.fail('추적 PNG 청크 길이가 잘못되었습니다.')
                raw.extend(header)
                remaining = size + 4
                while remaining:
                    chunk = self.read(min(65536,remaining)); raw.extend(chunk); remaining -= len(chunk)
                if header[4:] == b'IEND':
                    break
            self.index += 1
            actual = hashlib.sha256(raw).hexdigest()
            self.frames.observed_hashes[self.index] = actual
            expected = self.expected_hashes.get(self.index)
            if expected is not None and actual != expected:
                self.frames.fail('추적 픽셀이 기존 검수 표본과 다릅니다.')
            self.raw = raw
        if self.index == len(self.frames)-1:
            if self.process.stdout.read(1) or self.process.wait() != 0:
                self.frames.fail('추적 디코더가 정상 종료하지 못했습니다.')
            self.reader.join()
            if self.errors is not None:
                self.frames.fail('추적 디코더 로그를 저장하지 못했습니다.')
        return self.raw

    def close(self):
        failed = self.process.poll()
        try:
            if failed is None:
                self.process.kill()
            self.process.wait()
        finally:
            self.process.stdout.close()
            self.reader.join()
            self.process.stderr.close()
            self.log.close()
        if failed not in (None, 0) or self.errors is not None:
            self.frames.fail('추적 디코더가 정상 종료하지 못했습니다.')
