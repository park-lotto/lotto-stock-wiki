"""한글 경로에서 무음 감지가 조용히 죽지 않는지 — 실제 ffmpeg로 확인한다.

★2026-09-22 실사고: detect_silences/detect_edge_silence가 한글 경로에서 **항상** []/0.0을
반환했다. 무음이 없어서가 아니라 ffmpeg stderr(UTF-8)를 cp949로 디코드하다 리더 스레드가
죽고, `except Exception`이 그 예외를 삼켜 "무음 없음"으로 둔갑한 것이다.
→ 자동 자르기가 이 환경에서 한 번도 동작한 적이 없었다.

이 테스트는 **가짜 stderr 문자열이 아니라 진짜 mp3**를 만들어 돌린다. 문자열 파서만 재면
(test_edge_silence가 그렇다) 인코딩 사고를 영영 못 잡는다 — 그게 이번에 놓친 이유다.
"""
import shutil
import subprocess

import pytest

from shopping_shorts.audio_post import detect_edge_silence, detect_silences, extract_peaks

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


@pytest.fixture
def korean_mp3(tmp_path):
    """무음 1초 + 소리 1초 + 무음 1초짜리 3초 mp3를 **한글 폴더** 안에 만든다."""
    d = tmp_path / "로또의 주식" / "음성"
    d.mkdir(parents=True)
    out = d / "장면_0.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=1",
         "-filter_complex", "[1][0][1]concat=n=3:v=0:a=1", "-q:a", "4", str(out)],
        stdin=subprocess.DEVNULL, capture_output=True, check=True)
    return out


def test_detect_silences_works_on_korean_path(korean_mp3):
    """한글 경로에서도 무음 구간을 실제로 찾아야 한다(빈 목록 = 버그 재발)."""
    spans = detect_silences(str(korean_mp3), "-40dB", 0.2)
    assert spans, "한글 경로에서 무음을 못 찾았다 — 인코딩 버그 재발(리더 스레드 사망)"
    assert len(spans) >= 2, f"앞뒤 무음 2구간이 나와야 하는데 {spans}"


def test_detect_edge_silence_works_on_korean_path(korean_mp3):
    """앞뒤 각각 1초 무음을 실측해야 한다."""
    head = detect_edge_silence(str(korean_mp3), "head")
    tail = detect_edge_silence(str(korean_mp3), "tail")
    assert head > 0.5, f"앞 무음 1초를 못 쟀다(head={head})"
    assert tail > 0.5, f"뒤 무음 1초를 못 쟀다(tail={tail})"


def test_extract_peaks_on_korean_path(korean_mp3):
    """파형도 같은 경로에서 나와야 한다 — 가운데만 소리가 커야 맞다."""
    peaks = extract_peaks(str(korean_mp3), bars=120)
    assert len(peaks) == 120
    assert max(peaks[45:75]) > 0.05, "가운데 소리 구간이 비어 있다"
    assert max(peaks[:30]) < 0.05, "앞 무음 구간에 소리가 잡혔다"
