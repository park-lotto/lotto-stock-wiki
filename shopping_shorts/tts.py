"""ElevenLabs TTS로 EDL 비트별 새 나레이션 음성 생성(설계 §3-3).

ElevenLabs는 Gemini와 무관한 별도 API라 전용/공유 키풀 규칙과 무관(단일 키).
키가 없으면 개발용 무음 mp3를 반환해 파이프라인 E2E가 키 없이도 관통되게 한다.
"""
import time

import requests

from shopping_shorts import config

_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# 아주 짧은 무음 MP3(개발용 mock — 실제 음성 아님, 파이프라인 관통 목적).
_SILENT_MP3 = bytes.fromhex("fffb9004000000000000000000000000")


def _write_silent_mp3(out_path):
    with open(out_path, "wb") as f:
        f.write(_SILENT_MP3)


def synthesize_tts(text, out_path, voice_id=None, max_retries=3):
    """text → mp3(out_path). ElevenLabs 호출, 키 없으면 무음 mock. out_path 반환."""
    if not config.ELEVENLABS_API_KEY:
        _write_silent_mp3(out_path)
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
