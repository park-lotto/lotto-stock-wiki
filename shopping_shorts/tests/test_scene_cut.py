import subprocess
import pytest
from shopping_shorts import scene_cut


def _make_video(path, seconds=2, fps=30, with_audio=True, longer_audio=0.0):
    """테스트용 합성 영상. longer_audio>0이면 오디오가 비디오보다 그만큼 길다
    (실측: 릴스 3편 중 2편이 이 모양이었다 — 스펙 §3.5)."""
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", f"testsrc=size=320x568:rate={fps}:duration={seconds}"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i",
                f"sine=frequency=440:duration={seconds + longer_audio}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-c:a", "aac"]
    cmd += [str(path)]
    subprocess.run(cmd, check=True, capture_output=True, stdin=subprocess.DEVNULL)
    return path


def test_video_fps_reads_exact_rational(tmp_path):
    f = _make_video(tmp_path / "a.mp4", seconds=1, fps=30)
    assert scene_cut.video_fps(f) == 30.0


def test_video_frame_count_counts_video_not_audio(tmp_path):
    # 오디오가 0.5초 더 길다 — 컨테이너 길이를 쓰면 프레임 수가 부풀려진다
    f = _make_video(tmp_path / "b.mp4", seconds=2, fps=30, longer_audio=0.5)
    assert scene_cut.video_frame_count(f) == 60


def test_video_fps_raises_on_missing_file(tmp_path):
    with pytest.raises(RuntimeError):
        scene_cut.video_fps(tmp_path / "nope.mp4")
