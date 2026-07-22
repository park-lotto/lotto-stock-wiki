import subprocess
import pytest
from shopping_shorts.audio_post import _parse_silence_edges, detect_edge_silence

# ffmpeg silencedetect stderr 샘플: 앞 0.0~0.35 무음, 뒤 4.10~4.80 무음, 전체 4.80s
SAMPLE = (
    "[silencedetect @ 0x1] silence_start: 0\n"
    "[silencedetect @ 0x1] silence_end: 0.35 | silence_duration: 0.35\n"
    "[silencedetect @ 0x1] silence_start: 4.10\n"
    "[silencedetect @ 0x1] silence_end: 4.80 | silence_duration: 0.70\n"
)


def test_parse_head_silence():
    head, tail = _parse_silence_edges(SAMPLE, total_dur=4.80)
    assert abs(head - 0.35) < 1e-6


def test_parse_tail_silence():
    head, tail = _parse_silence_edges(SAMPLE, total_dur=4.80)
    assert abs(tail - 0.70) < 1e-6


def test_parse_no_silence_returns_zero():
    head, tail = _parse_silence_edges("", total_dur=3.0)
    assert head == 0.0 and tail == 0.0


def test_parse_tail_only_when_silence_reaches_end():
    # 끝에 안 닿는 중간 무음은 tail로 치지 않는다
    mid = ("[silencedetect] silence_start: 1.0\n"
           "[silencedetect] silence_end: 1.5 | silence_duration: 0.5\n")
    head, tail = _parse_silence_edges(mid, total_dur=4.0)
    assert head == 0.0 and tail == 0.0


def test_detect_edge_silence_returns_zero_on_probe_failure(monkeypatch):
    """_probe_duration 실패 시 detect_edge_silence는 0.0을 반환해야 한다."""
    import shopping_shorts.video_assemble

    def mock_probe_failure(path):
        raise subprocess.CalledProcessError(1, "ffprobe")

    monkeypatch.setattr(shopping_shorts.video_assemble, "_probe_duration", mock_probe_failure)
    result = detect_edge_silence("bad.mp3", "tail")
    assert result == 0.0


def test_detect_edge_silence_returns_zero_on_ffmpeg_failure(monkeypatch):
    """ffmpeg 실패 시 detect_edge_silence는 0.0을 반환해야 한다."""
    import shopping_shorts.video_assemble

    def mock_probe_success(path):
        return 5.0

    def mock_ffmpeg_failure(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "ffmpeg")

    monkeypatch.setattr(shopping_shorts.video_assemble, "_probe_duration", mock_probe_success)
    monkeypatch.setattr(subprocess, "run", mock_ffmpeg_failure)
    result = detect_edge_silence("bad.mp3", "tail")
    assert result == 0.0
