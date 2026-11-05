"""쉼을 맞춘 뒤 B18a 자로 다시 재서 모자란 만큼 늘린다 — 말 직전 작은 소리가 쉼을 자른 꼴(10-31 해외신기템 L4·L9)."""
import wave

import numpy as np

from tools.calcopy.hybrid.common import silences
from tools.calcopy.hybrid.render_bench import SR, pause_topup


def _voice():
    """말 1초 + 쉼 0.3초(끝에서 0.06초 전 잡음 0.01초) + 말 1초."""
    rng = np.random.default_rng(1)
    speak = lambda s: (rng.uniform(-.3, .3, int(s * SR))).astype(np.float32)
    quiet = lambda s: np.full(int(s * SR), 1e-4, np.float32)
    return np.concatenate([speak(1), quiet(.23), speak(.01), quiet(.06), speak(1)])


def _put(path):
    def put(v):
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(v, -1, 1) * 32767).astype("<i2").tobytes())
        return path
    return put


def _inner(path):
    return [round(b - a, 3) for a, b in silences(path, "-35dB", 0.08)]


def test_모자란_쉼을_검사_자로_채운다(tmp_path):
    p = tmp_path / "s.wav"
    y = _voice()
    tm = [(0.0, 0.0), (2.3, len(y) / SR)]
    _put(p)(y)
    assert max(_inner(p)) < .28          # 고치기 전에는 B18a 밖
    y2, tm2 = pause_topup(y, tm, [(1.15, .3)], _put(p))
    _put(p)(y2)
    assert .28 <= max(_inner(p)) <= .33
    assert tm2[-1][1] > tm[-1][1]        # 자막 시각도 같이 밀린다


def test_맞는_쉼은_건드리지_않는다(tmp_path):
    p = tmp_path / "s.wav"
    y = _voice()
    tm = [(0.0, 0.0), (2.3, len(y) / SR)]
    y2, tm2 = pause_topup(y, tm, [(1.15, .22)], _put(p))
    assert len(y2) == len(y) and tm2 == tm
