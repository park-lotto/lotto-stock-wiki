"""11-05 이준연 #7539: 원본 파일 끝을 넘는 영상 컷을 넘기기로 렌더하면 '컷 조각 프레임 모자람'으로 깨졌다 → 계획이 끝에 맞춰 앞당긴다."""
import subprocess
from pathlib import Path

from tools.calcopy.hybrid import render_bench as RB


def _vid(p: Path, sec: float):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=160x284:r=30:d={sec}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                   check=True, stdin=subprocess.DEVNULL)


def test_cut_past_file_end_is_pulled_back(tmp_path):
    _vid(tmp_path / "a.mp4", 10.0)
    c = {"line": "L9", "src": "a.mp4", "kind": "tts", "ss": 8.65, "t0": 0.0, "t1": 2.267, "dur": 2.267, "src_left": 1.3}
    assert RB.pull_to_end([c], tmp_path, log=lambda *_: None) == 1
    left = RB.src_left(tmp_path / "a.mp4", c["ss"])
    assert "src_left" not in c and left is not None and left >= round(RB.src_frames(c) / RB.FPS, 3) - 1e-3


def test_file_shorter_than_cut_is_left_alone(tmp_path):
    _vid(tmp_path / "b.mp4", 1.0)
    c = {"line": "L1", "src": "b.mp4", "kind": "tts", "ss": 0.2, "t0": 0.0, "t1": 3.0, "dur": 3.0, "src_left": 0.7}
    assert RB.pull_to_end([c], tmp_path, log=lambda *_: None) == 0 and c["ss"] == 0.2
