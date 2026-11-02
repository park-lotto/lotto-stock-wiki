"""인코더 주인 encoder.venc — CPU 는 지금까지와 같은 인자, GPU 실패는 같은 명령을 CPU 로(98 #79)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.engine import encoder  # noqa: E402


def _force(monkeypatch, k):
    monkeypatch.setattr(encoder, "_KIND", None)
    monkeypatch.setenv("SHORTEM_ENCODER", k)


def test_cpu_args_unchanged(monkeypatch):
    _force(monkeypatch, "cpu")
    assert encoder.venc(16) == ["-c:v", "libx264", "-crf", "16", "-preset", "veryfast"]
    assert encoder.venc(16, "medium")[-1] == "medium"


def test_gpu_args_and_cpu_retry(monkeypatch):
    _force(monkeypatch, "gpu")
    cmd = ["ffmpeg", "-i", "a.mp4", "-frames:v", "10", *encoder.venc(16), "-pix_fmt", "yuv420p", "out.mp4"]
    assert "h264_nvenc" in cmd and cmd[cmd.index("-cq") + 1] == "22"
    alt = encoder.cpu_retry(cmd)
    assert alt == ["ffmpeg", "-i", "a.mp4", "-frames:v", "10", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
                   "-pix_fmt", "yuv420p", "out.mp4"]
    assert encoder.kind() == "cpu"          # 한 번 실패하면 이 프로세스는 CPU 로
    assert encoder.cpu_retry(alt) is None   # CPU 명령은 다시 돌리지 않는다
