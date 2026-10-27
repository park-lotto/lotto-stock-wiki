"""자를 칸이 원본 밖이면 원본 안으로(10-27 run4 c편: 720×1280 원본에 1080 기준 칸 → 결과 0개로 3번 반복). 주인 = runner_ops.fit_crop."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def test_ref_coords_scaled_to_small_source():
    assert R.fit_crop([200, 900, 760, 1020], 720, 1280) == [133, 600, 506, 680]


def test_inside_untouched_and_outside_clamped():
    assert R.fit_crop([10, 10, 100, 100], 720, 1280) == [10, 10, 100, 100]
    x, y, w, h = R.fit_crop([0, 0, 2000, 4000], 1080, 1920)
    assert x + w <= 1080 and y + h <= 1920


def test_frames_reports_failure_instead_of_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "frame", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffmpeg 실패")))
    out = R.c_frames(tmp_path, {"src": "a.mp4", "items": [{"t": 1}], "prefix": "p_"})
    assert out["files"] == [] and "ffmpeg 실패" in out["error"]
