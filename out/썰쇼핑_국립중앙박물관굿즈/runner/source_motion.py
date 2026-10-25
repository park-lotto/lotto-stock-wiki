"""Source-content pixel motion, independent of semantic review and refinement.

Callers own the source read guard. No detector, semantic question or quality
threshold belongs here. Always use the issued raw sample seeks on first
measurement; only the source/extraction-bound scalar receipt is reusable.
"""
import hashlib
import json
import math
import shutil
import threading
from pathlib import Path


_TOOL_IDENTITIES = {}
_TOOL_LOCK = threading.Lock()


def _tool_identity(command):
    """Fingerprint the executing binary once per unchanged filesystem object."""
    import volcano_run as R
    path = Path(shutil.which(command) or command).resolve()
    def stamp():
        st = path.stat()
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    with _TOOL_LOCK:
        before = stamp(); key = (str(path), before)
        value = _TOOL_IDENTITIES.get(key)
        if value is None:
            value = dict(path=str(path), sha256=R._image_file_sha(path))
            if stamp() != before:
                raise R.StepError('움직임 추출 도구가 측정 중 바뀌었습니다.')
            _TOOL_IDENTITIES[key] = value
        return dict(value)


def extraction(cut):
    import PIL
    import numpy as np
    argv = cut.get('frame_argv')
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) for a in argv):
        raise ValueError('원본 움직임의 프레임 추출 명령이 필요합니다.')
    return dict(argv=list(argv), suffix=cut.get('suffix') or '.ppm',
                tool=_tool_identity(argv[0]), pixels='PIL-L/int16-abs-mean/median-v1',
                pillow=PIL.__version__, numpy=np.__version__)


def recipe(cut, content, source_identity):
    samples = cut.get('samples')
    if (not isinstance(samples, list) or len(samples) < 2
            or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in samples)
            or samples != sorted(set(samples))):
        raise ValueError('원본 움직임을 잴 순서 있는 표본 시각이 필요합니다.')
    if (not isinstance(content, (list, tuple)) or len(content) != 4
            or any(type(v) is not int for v in content)
            or min(content[:2]) < 0 or min(content[2:]) <= 0):
        raise ValueError('원본 움직임의 알맹이 사각형이 잘못되었습니다.')
    return dict(version=4, extraction=extraction(cut), source_identity=source_identity, content=list(content),
                samples=list(samples), start=float(cut['start']),
                duration=float(cut['duration']), fps=float(cut['fps']))


def pixel_value(grays, content):
    import numpy as np
    x, y, w, h = content
    if not grays or any(g.ndim != 2 or y+h > g.shape[0] or x+w > g.shape[1] for g in grays):
        raise ValueError('원본 움직임 표본이 없거나 알맹이 사각형 밖입니다.')
    parts = [g[y:y+h, x:x+w].astype(np.int16) for g in grays]
    diffs = [float(np.abs(b-a).mean()) for a, b in zip(parts, parts[1:])]
    return float(np.median(diffs)) if diffs else 0.0


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def measure(cut, content, source_identity, directory, *, before_measure=None):
    """Measure exact issued raw frames once; reuse only the verified scalar."""
    import numpy as np
    from PIL import Image
    import volcano_run as R
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    request = recipe(cut, content, source_identity)
    target = directory / ('source-motion-' + _digest(request) + '.json')
    with R.review_receipt_lock(str(target)):
        try:
            saved = json.loads(target.read_text(encoding='utf-8'))
            value = saved['value']
            if (saved['request'] == request and type(value) in (int, float)
                    and math.isfinite(value) and value >= 0
                    and saved['sha256'] == _digest(dict(request=request, value=value))):
                return dict(request, value=value)
        except (OSError, ValueError, TypeError, KeyError):
            pass
        if before_measure: before_measure()
        grays = []
        for sample, t in enumerate(cut['samples']):
            path = directory / ('motion-' + _digest(dict(request=request, sample=sample)) + request['extraction']['suffix'])
            path.unlink(missing_ok=True)
            argv = [a.replace('@@T@@', f'{float(t):.6f}').replace('@@OUT@@', str(path))
                    for a in cut['frame_argv']]
            result = R._spawn(argv, capture_output=True)
            if result.returncode or not path.is_file():
                raise R.StepError('원본 움직임 표본을 측정하지 못했습니다. 같은 장면이나 검수를 반복하지 않습니다.')
            with Image.open(path) as image:
                grays.append(np.asarray(image.convert('L')))
        if extraction(cut) != request['extraction']:
            raise R.StepError('움직임 추출 도구가 측정 중 바뀌었습니다.')
        value = pixel_value(grays, content)
        saved = dict(request=request, value=value)
        R._photo_write_state(str(target), dict(saved, sha256=_digest(saved)))
        return dict(request, value=value)
