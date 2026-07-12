"""ElevenLabs TTS로 EDL 비트별 새 나레이션 음성 생성(설계 §3-3).

ElevenLabs는 Gemini와 무관한 별도 API라 전용/공유 키풀 규칙과 무관(단일 키).
키가 없으면 개발용 무음 mp3를 반환해 파이프라인 E2E가 키 없이도 관통되게 한다.
"""
import subprocess
import time

import requests

from shopping_shorts import config

_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# 한국어 발화속도 근사치(초당 글자수). 무음 mock 길이 추정용.
_CHARS_PER_SEC = 5.0
_MIN_MOCK_SEC = 1.0
_MAX_MOCK_SEC = 15.0


def _estimate_seconds(text):
    """나레이션 텍스트 길이 → 대략적 발화시간(초). 한국어 초당 5자 가정, [1.0, 15.0] clamp."""
    n = len((text or "").strip())
    return max(_MIN_MOCK_SEC, min(_MAX_MOCK_SEC, n / _CHARS_PER_SEC))


def _write_silent_mp3(out_path, seconds):
    """ffmpeg로 ffprobe 가능한 실제 무음 mp3 생성(개발용 mock — 실제 음성 아님,
    파이프라인 관통 목적). anullsrc로 무음 오디오를 지정 길이만큼 인코딩한다."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", f"{seconds:.2f}", "-q:a", "9", str(out_path)],
        stdin=subprocess.DEVNULL, capture_output=True, check=True,
    )


def synthesize_tts(text, out_path, voice_id=None, max_retries=3):
    """text → mp3(out_path). ElevenLabs 호출, 키 없으면 무음 mock. out_path 반환."""
    if not config.ELEVENLABS_API_KEY:
        _write_silent_mp3(out_path, _estimate_seconds(text))
        return out_path
    vid = voice_id or config.ELEVENLABS_VOICE_ID
    url = _ENDPOINT.format(voice_id=vid)
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {"text": text, "model_id": "eleven_multilingual_v2"}
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 2)
                continue
            raise
    return out_path
