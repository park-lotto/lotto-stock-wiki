import subprocess
from pathlib import Path
import pytest
from shopping_shorts import frame_extract


def test_download_video_writes_file(monkeypatch, tmp_path):
    class FakeResp:
        status_code = 200
        def iter_content(self, chunk_size):
            yield b"fake video bytes"
        def raise_for_status(self):
            pass
    def fake_get(url, stream=True, timeout=None):
        assert url == "https://example.com/v.mp4"
        return FakeResp()
    monkeypatch.setattr(frame_extract.requests, "get", fake_get)

    path = frame_extract.download_video("https://example.com/v.mp4", tmp_path)

    assert path.exists()
    assert path.read_bytes() == b"fake video bytes"
    assert path.parent == tmp_path


def test_extract_frames_calls_ffmpeg_and_returns_existing_files(monkeypatch, tmp_path):
    video_path = tmp_path / "in.mp4"
    video_path.write_bytes(b"fake")

    calls = []
    def fake_run(cmd, capture_output=True, check=False):
        calls.append(cmd)
        # ffmpeg가 만들었을 프레임 파일들을 테스트가 직접 생성해 시뮬레이션
        for i in range(3):
            (tmp_path / f"frame_{i+1}.jpg").write_bytes(b"jpg")
        class FakeResult:
            returncode = 0
            stderr = b""
        return FakeResult()
    monkeypatch.setattr(frame_extract.subprocess, "run", fake_run)

    frames = frame_extract.extract_frames(video_path, tmp_path, max_frames=6)

    assert len(calls) == 1
    assert "ffmpeg" in calls[0][0]
    assert len(frames) == 3
    assert all(f.exists() for f in frames)


def test_extract_frames_raises_on_ffmpeg_failure(monkeypatch, tmp_path):
    video_path = tmp_path / "in.mp4"
    video_path.write_bytes(b"fake")

    def fake_run(cmd, capture_output=True, check=False):
        class FakeResult:
            returncode = 1
            stderr = b"ffmpeg: error decoding"
        return FakeResult()
    monkeypatch.setattr(frame_extract.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        frame_extract.extract_frames(video_path, tmp_path, max_frames=6)


def test_extract_frame_at_returns_path_on_success(monkeypatch, tmp_path):
    video_path = tmp_path / "in.mp4"
    video_path.write_bytes(b"fake")

    calls = []
    def fake_run(cmd, capture_output=True, check=False):
        calls.append(cmd)
        (tmp_path / "frame_hint.jpg").write_bytes(b"jpg")
        class FakeResult:
            returncode = 0
            stderr = b""
        return FakeResult()
    monkeypatch.setattr(frame_extract.subprocess, "run", fake_run)

    result = frame_extract.extract_frame_at(video_path, tmp_path, 12.5)

    assert result == tmp_path / "frame_hint.jpg"
    assert result.exists()
    assert "12.5" in calls[0]


def test_extract_frame_at_returns_none_on_ffmpeg_failure(monkeypatch, tmp_path):
    video_path = tmp_path / "in.mp4"
    video_path.write_bytes(b"fake")

    def fake_run(cmd, capture_output=True, check=False):
        class FakeResult:
            returncode = 1
            stderr = b"ffmpeg: error"
        return FakeResult()
    monkeypatch.setattr(frame_extract.subprocess, "run", fake_run)

    assert frame_extract.extract_frame_at(video_path, tmp_path, 5) is None
