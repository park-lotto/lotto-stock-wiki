"""ONNX Runtime execution provider choice for in-render AI — one place per PC (2026-10-19).

Owner decision 10-19 «GPU 가 있는 사람은 가속 기능을 최대한 활용 · 모든 프리셋».
Measured (memory gpu-encode-all-presets-decided-1019): ACNet 300 frames — win-main RX 5700 XT
CPU 13.7s / DirectML 3.5s · win-01 GTX 1060 CPU 16.7s / DirectML 4.1s; GPU vs CPU output differs by at most
one 8-bit step (Mac CPU vs Windows CPU already differed by one step too).

* Windows with the `onnxruntime-directml` wheel and a DirectX 12 device → 'dml'
  (['DmlExecutionProvider', 'CPUExecutionProvider']); everything else → 'cpu'.
  macOS CoreML is deliberately not used: one stuck CoreML session stalls every later one and the gain was 1.16x.
* The choice is probed once per PC in a child process (a driver crash or hang cannot take the runner down)
  and remembered in ~/.volcano/onnx_providers.json, keyed by onnxruntime version + install path + GPU driver.
* A DirectML failure during real work marks this key 'cpu' in that file (persisted — a rerun must not hit the
  same failure again) and callers redo the work on CPU once. No retry beyond that.

Official DirectML EP requirements (onnxruntime docs, execution-providers/DirectML-ExecutionProvider.md):
`enable_mem_pattern = False`, `execution_mode = ORT_SEQUENTIAL`, and only one thread may call Run on a session
at a time — `Session.run` holds a lock for DML sessions.
"""
import json
import os
import struct
import subprocess
import sys
import threading
import time

CACHE_VERSION = 1
PROBE_TIMEOUT = 120
DML = 'DmlExecutionProvider'
CPU = 'CPUExecutionProvider'

_lock = threading.Lock()
_probe_lock = threading.Lock()
_memo = {}


class GpuFailed(RuntimeError):
    """DirectML could not build or run a session — the caller redoes the work on CPU once."""


def cache_path():
    return os.path.join(os.path.expanduser('~'), '.volcano', 'onnx_providers.json')


def _load():
    try:
        with open(cache_path(), encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(key, record):
    path = cache_path()
    try:
        data = _load()
        data[key] = record
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f'{path}.{os.getpid()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError as e:          # the choice still holds for this process
        print(f'  ⚠ AI 처리 장치 판정 기록을 못 남겼습니다({e}) — 다음 실행에서 다시 시험합니다', file=sys.stderr, flush=True)


def _key(ort):
    from video_encoder import _gpu_driver
    return json.dumps([CACHE_VERSION, ort.__version__, os.path.realpath(os.path.dirname(ort.__file__)), _gpu_driver()],
                      ensure_ascii=False)


# ── probe model: Conv(3x3, pads 1) → Relu, 1x1x16x16 → 1x4x16x16 (ONNX protobuf written by hand — no `onnx` package)
def _varint(n):
    out = bytearray()
    while True:
        b, n = n & 0x7F, n >> 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _f(field, value):
    if isinstance(value, int):
        return _varint(field << 3) + _varint(value)
    value = value.encode() if isinstance(value, str) else value
    return _varint(field << 3 | 2) + _varint(len(value)) + value


def _value_info(name, dims):
    shape = b''.join(_f(1, _f(1, d)) for d in dims)
    return _f(1, name) + _f(2, _f(1, _f(1, 1) + _f(2, shape)))


def _tensor(name, dims, values):
    return b''.join(_f(1, d) for d in dims) + _f(2, 1) + _f(8, name) + _f(9, struct.pack(f'<{len(values)}f', *values))


def probe_model():
    weights = [((i * 7 + 3) % 11 - 5) / 10 for i in range(4 * 9)]
    conv = (_f(1, 'x') + _f(1, 'w') + _f(1, 'b') + _f(2, 'c') + _f(4, 'Conv')
            + _f(5, _f(1, 'pads') + b''.join(_f(8, 1) for _ in range(4)) + _f(20, 7)))
    relu = _f(1, 'c') + _f(2, 'out') + _f(4, 'Relu')
    graph = (_f(1, conv) + _f(1, relu) + _f(2, 'volcano-probe') + _f(5, _tensor('w', (4, 1, 3, 3), weights))
             + _f(5, _tensor('b', (4,), [0.1, -0.1, 0.0, 0.05]))
             + _f(11, _value_info('x', (1, 1, 16, 16))) + _f(12, _value_info('out', (1, 4, 16, 16))))
    return _f(1, 8) + _f(2, 'volcano') + _f(7, graph) + _f(8, _f(1, '') + _f(2, 17))


def options(ort, name):
    so = ort.SessionOptions()
    if name == 'dml':
        so.enable_mem_pattern = False
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return so


def _child_probe():
    """Child process: build the probe model on DML and CPU, compare outputs → one JSON line."""
    import numpy as np
    import onnxruntime as ort
    model = probe_model()
    x = (np.arange(256, dtype=np.float32).reshape(1, 1, 16, 16) % 17) / np.float32(16)
    dml = ort.InferenceSession(model, options(ort, 'dml'), providers=[DML, CPU])
    if dml.get_providers()[0] != DML:
        raise RuntimeError('DirectML provider was not attached: ' + ','.join(dml.get_providers()))
    got = dml.run(None, {'x': x})[0]
    ref = ort.InferenceSession(model, options(ort, 'cpu'), providers=[CPU]).run(None, {'x': x})[0]
    err = float(np.abs(got - ref).max())
    if not err < 1e-3:
        raise RuntimeError(f'DirectML output differs from CPU by {err}')
    print(json.dumps({'ok': True, 'max_error': err}))


def _probe():
    t0 = time.monotonic()
    try:
        p = subprocess.run([sys.executable, os.path.abspath(__file__), '--probe'], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=PROBE_TIMEOUT)
        ok = p.returncode == 0 and '"ok": true' in (p.stdout or '')
        why = '' if ok else ((p.stderr or p.stdout or '').strip().splitlines() or [f'exit {p.returncode}'])[-1]
    except (OSError, subprocess.SubprocessError) as e:
        ok, why = False, str(e)
    return {'ok': ok, 'why': why[-300:], 'sec': round(time.monotonic() - t0, 2)}


def _windows():
    return os.name == 'nt'


def choice():
    """'dml' or 'cpu' for this PC (probes once per key, then the file answers)."""
    with _lock:
        if 'name' in _memo:
            return _memo['name']
    with _probe_lock:
        with _lock:
            if 'name' in _memo:
                return _memo['name']
        name, key = 'cpu', None
        if _windows():
            import onnxruntime as ort
            if DML in ort.get_available_providers():
                key = _key(ort)
                hit = (_load().get(key) or {}).get('chosen')
                if hit in ('dml', 'cpu'):
                    name = hit
                else:
                    tried = _probe()
                    name = 'dml' if tried['ok'] else 'cpu'
                    _save(key, {'chosen': name, 'tried': tried, 'at': int(time.time())})
                    print(f"  [AI 처리] {'그래픽카드(DirectML)' if name == 'dml' else 'CPU'} 로 돌립니다"
                          f"(시험 {'성공' if tried['ok'] else '실패 — ' + tried['why']})", file=sys.stderr, flush=True)
        with _lock:
            _memo.update(name=name, key=key)
        return name


def mark_broken(error):
    """DirectML failed during real work → CPU from now on, for this process and this PC key."""
    with _lock:
        was, key = _memo.get('name'), _memo.get('key')
        _memo['name'] = 'cpu'
    if was == 'dml':
        print(f'  ⚠ 그래픽카드 AI 처리가 실패해 CPU 로 한 번 다시 합니다: {str(error)[-300:]}', file=sys.stderr, flush=True)
        if key:
            _save(key, {'chosen': 'cpu', 'tried': {'ok': False, 'why': ('run: ' + str(error))[-300:]}, 'at': int(time.time())})


class Session:
    """InferenceSession plus the provider it runs on. DML runs are serialised (official: one Run per session)."""

    def __init__(self, model, name):
        import onnxruntime as ort
        self.provider = name
        self._lock = threading.Lock() if name == 'dml' else None
        try:
            self._s = ort.InferenceSession(model, options(ort, name), providers=[DML, CPU] if name == 'dml' else [CPU])
            if name == 'dml' and self._s.get_providers()[0] != DML:
                raise RuntimeError('DirectML provider was not attached')
        except Exception as e:
            if name == 'dml':
                raise GpuFailed(str(e)) from e
            raise

    def run(self, outputs, feeds):
        if self._lock is None:
            return self._s.run(outputs, feeds)
        try:
            with self._lock:
                return self._s.run(outputs, feeds)
        except Exception as e:
            raise GpuFailed(str(e)) from e


def with_cpu_fallback(work):
    """work() once on this PC's choice; on GpuFailed mark DML broken and run work() once more (now CPU)."""
    try:
        return work()
    except GpuFailed as e:
        mark_broken(e)
        return work()


if __name__ == '__main__' and sys.argv[1:] == ['--probe']:
    _child_probe()
