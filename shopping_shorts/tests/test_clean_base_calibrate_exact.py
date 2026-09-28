"""CAL v5 — frame_exact 정본도 잰다(2026-09-27). 칸 안 컷 경계 수리(05:11) 전 청소본은 frame_exact 표식이 붙어도 컷마다 밀려 있었다
(39e55470ebb0 02:06 청소본: 칸 안 +1→+3, 뒤 칸 −3프레임 → 보정을 건너뛰어 완성본이 화면보다 3프레임 앞섬).
규칙: frame_exact 정본은 2프레임(EXACT_MIN) 이상 어긋난 컷만, 그리고 전 구간 대조(_geom_resid)에서 **실제로 더 맞을 때만** 좌표를 고친다.
합성: 무늬 원본 + 가짜 청소본(컷 셋 중 가운데만 3프레임 늦게 붙임) · 맞는 정본(전부 0).
"""
import shutil
import subprocess

import numpy as np
import pytest

from shopping_shorts import clean_base as cb

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")

FPS = 30
CUTS = [(0.0, 1.0), (1.2, 1.0), (2.4, 1.0)]          # (원본 시작, 길이) — 전부 1배속


def _pattern(rng):
    g = rng.integers(0, 256, size=(16, 9), dtype=np.uint8)
    img = np.kron(g, np.ones((10, 10), np.uint8))
    return np.repeat(img[:, :, None], 3, axis=2)


def _encode(frames, path):
    h, w = frames.shape[1:3]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
                    "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-g", "1", "-pix_fmt", "yuv444p",
                    str(path)], input=frames.tobytes(), check=True, timeout=60)


def _make(tmp_path, lags):
    rng = np.random.default_rng(11)
    src = np.stack([_pattern(rng) for _ in range(int(3.6 * FPS))])
    _encode(src, tmp_path / "src.mp4")
    n = int(round((sum(d for _s, d in CUTS) + 0.5) * FPS))
    clean = np.stack([_pattern(rng) for _ in range(n)])
    fin = 0.0
    fins = []
    for (s0, d), lag in zip(CUTS, lags):
        fins.append(fin)
        for i in range(int(round(d * FPS))):
            j = int(round(fin * FPS)) + lag + i
            if 0 <= j < n:
                clean[j] = src[int(round(s0 * FPS)) + i]
        fin += d
    _encode(clean, tmp_path / "final_clean_e.mp4")
    cuts = [{"beat_idx": k, "video_id": "v", "src": s0, "sdur": d, "dur": d, "fin": round(f, 3), "cleaned": True}
            for k, ((s0, d), f) in enumerate(zip(CUTS, fins))]
    return {"sig": "e", "path": str(tmp_path / "final_clean_e.mp4"), "cuts": cuts, "beat_keys": {}, "extras": {},
            "frame_exact": True}


def test_exact_base_fixes_only_shifted_cut(tmp_path):
    base = _make(tmp_path, [0, 3, 0])
    out = cb.calibrate(tmp_path, base, {"v": str(tmp_path / "src.mp4")})
    assert out["calibrated"] == cb.CAL_VERSION == 5
    offs = [c.get("off") for c in out["cuts"]]
    assert offs[0] is None and offs[2] is None, offs                    # 맞는 컷은 안 건드린다
    assert offs[1] is not None and abs(offs[1] - 3 / FPS) <= 1 / FPS + 1e-6, offs


def test_exact_base_correct_file_untouched(tmp_path):
    base = _make(tmp_path, [0, 0, 0])
    out = cb.calibrate(tmp_path, base, {"v": str(tmp_path / "src.mp4")})
    assert all(c.get("off") is None and c.get("off_end") is None for c in out["cuts"]), out["cuts"]
    assert out["calibrated"] == 5


def test_one_frame_noise_not_applied(tmp_path):
    """1프레임 어긋남은 frame_exact 정본에선 잡음으로 보고 안 고친다(EXACT_MIN = 2프레임)."""
    base = _make(tmp_path, [0, 1, 0])
    out = cb.calibrate(tmp_path, base, {"v": str(tmp_path / "src.mp4")})
    assert all(c.get("off") is None for c in out["cuts"]), out["cuts"]
