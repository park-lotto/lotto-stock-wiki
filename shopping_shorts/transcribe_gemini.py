"""Gemini 멀티모달로 영상/오디오 나레이션을 그대로 전사(대본 추출).

watch 스킬은 Groq/OpenAI Whisper만 지원하지만, 이 프로젝트엔 이미 Gemini
파이프라인(key_vault)이 있으므로 Whisper 키 없이 Gemini로 전사한다.

사용:
    python -m shopping_shorts.transcribe_gemini <audio_or_video_path>

오디오/짧은 영상 파일을 Gemini File API로 업로드 → 나레이션을 한국어 그대로 전사.
"""
import sys
import time
from pathlib import Path

from google.genai import types
from pipeline.atoms import key_vault

_GROUP = "general"
_MODEL = "gemini-3.1-flash-lite"

_PROMPT = """이 오디오(영상 나레이션)를 **말한 그대로 한국어로 전사**하라.

규칙:
- 실제로 들리는 말을 최대한 정확히 받아써라. 요약·의역 금지.
- 화면 자막이나 배경음악 가사가 아니라 **나레이션/화자의 말**을 우선.
- 문장 단위로 줄바꿈. 각 문장 앞에 대략적 타임스탬프 [MM:SS] 붙여라(모르면 생략).
- 말이 없고 음악만 있으면 "(나레이션 없음 — 배경음악만)"이라고만 답하라.
- 군더더기 설명 없이 전사 결과만 출력.
"""


def transcribe(path: str, max_retries: int = 4) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    for attempt in range(max_retries):
        try:
            client = key_vault.get_client(_GROUP)
            uploaded = client.files.upload(file=str(p))
            # 업로드 처리 대기 (ACTIVE 될 때까지)
            for _ in range(30):
                info = client.files.get(name=uploaded.name)
                state = getattr(info.state, "name", str(info.state))
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    raise RuntimeError(f"파일 처리 실패: {uploaded.name}")
                time.sleep(2)
            resp = client.models.generate_content(
                model=_MODEL,
                contents=[uploaded, _PROMPT],
            )
            return (resp.text or "").strip()
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e):
                if key_vault.rotate(_GROUP):
                    continue
                raise
            if key_vault.is_quota_error(e):
                time.sleep(3)
                continue
            raise
    raise RuntimeError("전사 실패 (재시도 소진)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m shopping_shorts.transcribe_gemini <audio_or_video>", file=sys.stderr)
        sys.exit(1)
    print(transcribe(sys.argv[1]))
