# -*- coding: utf-8 -*-
"""cutdet 프레임 특징을 조각마다 차례로 재도 옛 통째 계산과 값이 같은가 + 프레임을 안 쌓는가(98 #101).

10-25 기미 flowtest: 1592초 가로 원본을 render_bench.shot_starts 가 cutdet 으로 통째 읽어 (47712,360,360) float32 = 23GiB → MemoryError,
품질 관문 '컷 끝 번쩍임' 이 미측정. 주인 = readline_tools.cutdet.frame_feats(조각 읽기) · render_bench._src_cuts 는 shots=False 로 부른다.
1) 무작위 프레임을 조각 크기 7 로 나눠도 mean·sharp·diff·hd 가 옛 통째 식(아래 _old_feats = 10-25 이전 cutdet 본문)과 비트까지 같다.
2) keep=False 면 F 를 안 만든다(메모리가 영상 길이와 무관). keep=True 면 F 가 옛 F 와 같다.
3) 합성 mp4: cutdet(shots=False) 의 cuts 가 기본 호출과 같다.
사보타주: 조각 경계에서 prev 를 잇지 않으면(diff 를 조각마다 0 부터) 1)이 깨진다(작성 때 확인)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from tools.calcopy.engine.readline_tools import cutdet  # noqa: E402


def _old_feats(raw: np.ndarray, h: int):
    F = raw.astype(np.float32)
    n = len(F)
    mean = F.mean((1, 2))
    sharp = np.array([cv2.Laplacian(f[:int(h * 0.55)], cv2.CV_32F).var() for f in F])
    diff = np.r_[0, [np.abs(F[i] - F[i - 1]).mean((0, 1)) for i in range(1, n)]] if n > 1 else np.zeros(n)
    hist = [cv2.calcHist([f.astype(np.uint8)], [0], None, [32], [0, 256]).ravel() for f in F]
    hist = [x / x.sum() for x in hist]
    hd = np.r_[0, [0.5 * np.abs(hist[i] - hist[i - 1]).sum() for i in range(1, n)]]
    return n, mean, sharp, diff, hd, F


def _chunks(U, k):
    for i in range(0, len(U), k):
        yield U[i:i + k]


@pytest.mark.parametrize("k", [1, 7, 50, 1000])
def test_stream_feats_equal_old(k):
    rng = np.random.default_rng(3)
    h, w = 40, 36
    U = rng.integers(0, 256, (50, h, w), dtype=np.uint8)
    U[20:] //= 3                                                   # 밝기 점프 하나(컷 후보)
    on, om, osh, od, ohd, oF = _old_feats(U, h)
    for keep in (False, True):
        n, m, sh, d, hd, F = cutdet.frame_feats(_chunks(U, k), h, w, keep)
        assert n == on
        assert m.tobytes() == om.tobytes() and sh.tobytes() == osh.tobytes()
        assert d.tobytes() == od.tobytes() and hd.tobytes() == ohd.tobytes()
        assert cutdet.cut_groups(d, hd) == cutdet.cut_groups(od, ohd)
        if keep:
            assert F.tobytes() == oF.tobytes()
        else:
            assert F is None


def test_stream_does_not_keep_frames():
    """keep=False 면 조각을 넘긴 뒤 붙잡지 않는다 — 조각마다 새 버퍼를 줘도 살아 있는 조각은 한두 개."""
    import weakref
    h, w = 30, 30
    alive = []

    def gen():
        for i in range(40):
            a = np.full((5, h, w), i % 256, np.uint8)
            alive.append(weakref.ref(a))
            yield a
    cutdet.frame_feats(gen(), h, w, keep=False)
    import gc
    gc.collect()
    assert sum(r() is not None for r in alive) <= 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")
def test_cutdet_shots_false_same_cuts(tmp_path):
    W, H, FPS = 320, 568, 30
    mp4 = str(tmp_path / "s.mp4")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", mp4], stdin=subprocess.PIPE)
    rng = np.random.default_rng(5)
    for i in range(600):                                           # 20초 — 조각(256) 경계를 두 번 넘는다
        base = (40 + 60 * (i // 90)) % 256
        f = np.full((H, W), base, np.uint8)
        f[100:300, 50 + (i % 90):150 + (i % 90)] = 230
        f[400:420] = rng.integers(0, 255, (20, W), dtype=np.uint8)
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0
    a = cutdet.cutdet(mp4, 0, H, 30.0, W)
    b = cutdet.cutdet(mp4, 0, H, 30.0, W, shots=False)
    assert a["n"] == b["n"] == 600
    assert a["cuts"] == b["cuts"] and len(a["cuts"]) >= 5
    assert b["shots"] is None and len(a["shots"]) == len(a["cuts"]) + 1
