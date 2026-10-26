"""한 장 뽑기 끝 시각(10-27 실사고): 41.93초 재료 영상에서 얼굴 검사가 41.92초를 뽑다 ffmpeg 실패 → 장면 계획 실패로 편이 멈춤.
runner_ops.frame 은 영상 끝 바로 앞·밖 시각도 그림을 낸다 · 실행기 안에 '-ss … -frames:v 1' 한 장 뽑기를 frame 밖에서 새로 쓰지 않는다."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def test_frame_at_or_past_end_still_writes(tmp_path):
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=30", "-t", "2.0", "-pix_fmt", "yuv420p", str(v)], check=True)
    for t in (1.99, 2.0, 5.0):
        out = tmp_path / f"f_{t}.jpg"
        R.frame(v, t, out)
        assert out.exists() and out.stat().st_size > 0, t


def test_no_point_grab_outside_frame():
    src = (ROOT / "tools/calcopy/hybrid/runner_ops.py").read_text(encoding="utf-8")
    body = src.split("def frame(", 1)[1].split("\ndef ", 1)[1]          # frame 함수 밖(뒤쪽 전부)
    bad = [ln.strip()[:120] for ln in body.splitlines() if re.search(r'"-ss", f"\{t:', ln) and '"-frames:v", "1"' in ln]
    assert not bad, bad
