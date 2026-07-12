"""S급 대본의 '구조'를 Gemini로 분석 — 훅유형·비트순서·타이밍·수사장치 태깅.

생성 단계는 이 구조를 '뼈대'로 재사용한다(대본 텍스트를 통째로 베끼는 게 아니라
검증된 구조 위에 새 내용을 입힌다). 위키(도서관)에 담을 때 1회 분석해 저장한다.
전용 키풀(SHORTS_GEMINI_KEYS)을 comment_gen 로테이션으로 재사용. 실패 시 빈 dict.
"""
import json

from google.genai import types

from shopping_shorts import comment_gen

_MODEL = comment_gen._MODEL

_SCHEMA = {
    "type": "object",
    "properties": {
        "hook_type": {"type": "string"},
        "hook_line": {"type": "string"},
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "desc": {"type": "string"},
                    "approx_sec": {"type": "string"},
                },
                "required": ["label", "desc"],
            },
        },
        "devices": {"type": "array", "items": {"type": "string"}},
        "target_seconds": {"type": "number"},
        "one_line_why": {"type": "string"},
    },
    "required": ["hook_type", "hook_line", "beats", "devices", "one_line_why"],
}

_PROMPT = """너는 바이럴 숏폼 대본을 해부하는 분석가다. 아래 대본이 '왜 잘 터졌는지'
그 구조를 뽑아내라(내용 요약이 아니라 재사용 가능한 뼈대).

[대본 전체]
{full_text}

다음을 채워라:
- hook_type: 첫 훅의 유형을 한 단어로. 예: 경고형("절대 하지 마세요"), 반전형("알고보니"),
  권위인용형("이모님이 알려준"), 호기심갭형("99%가 모르는"), 공감형("저도 그랬어요"),
  실수지적형, 비교형 중 가장 가까운 것(없으면 새로 명명).
- hook_line: 실제 첫 훅 문장 그대로.
- beats: 시간 순서의 '비트' 배열. 각 비트는 label(훅|문제제기|공감|반전|증거/시연|결과|CTA 등),
  desc(그 비트가 하는 역할 한 줄), approx_sec("0-2" 같은 대략 구간).
- devices: 사용된 수사·설득 장치들(예: 권위자인용, 구체적숫자, 감정트리거, 비포애프터,
  손실회피, 시연, 반문). 해당되는 것만.
- target_seconds: 전체 영상 길이 추정(초).
- one_line_why: 이 대본이 잘 먹힌 핵심 이유 한 줄.

JSON만 출력."""


def analyze_structure(full_text, max_key_tries=3):
    """대본 전체 텍스트 → 구조 dict. 실패/무키면 {}."""
    if not comment_gen.SHORTS_GEMINI_KEYS or not (full_text or "").strip():
        return {}
    prompt = _PROMPT.format(full_text=full_text[:4000])
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return {}
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 — 분석 실패는 치명적 아님(빈 구조로 저장)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            return {}
    return {}
