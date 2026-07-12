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
        "narrator": {"type": "string"},
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"who": {"type": "string"}, "role": {"type": "string"}},
                "required": ["who", "role"],
            },
        },
        "storyline": {"type": "string"},
        "development": {"type": "string"},
        "twist": {"type": "string"},
        "appeal": {"type": "string"},
        "tone": {"type": "string"},
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
    "required": ["hook_type", "hook_line", "narrator", "characters", "storyline",
                 "development", "appeal", "tone", "beats", "devices", "one_line_why"],
}

_PROMPT = """너는 바이럴 숏폼 대본을 해부하는 분석가다. 아래 대본이 '왜 잘 터졌는지'
그 구조를 뽑아내라(내용 요약이 아니라 재사용 가능한 뼈대). 특히 이 니치의 핵심
기법인 '자연스러운 스토리텔링'(누가·어떤 주변인물을 등장시켜·어떻게 이야기를
끌고 가는지)을 정밀하게 잡아내라.

[대본 전체]
{full_text}

다음을 채워라:
- hook_type: 첫 훅 유형을 한 단어로. 예: 경고형("절대 하지 마세요"), 반전형("알고보니"),
  권위인용형("이모님이 알려준"), 호기심갭형("99%가 모르는"), 공감형("저도 그랬어요"),
  실수지적형, 비교형 중 가장 가까운 것(없으면 새로 명명).
- hook_line: 실제 첫 훅 문장 그대로.
- narrator: 화자가 누구인가(누구 시점으로 말하나). 예: "직접(나)", "지인 의사 인용",
  "김밥집 사장님 시점".
- characters: 이야기에 '등장시킨 주변인물'과 그 역할. 이게 핵심 기법이다 — 나와 관련된
  주변인(예: 부산에서 장사하신 이모님, 병원 하는 지인, 김밥집 사장님)을 오버하지 않고
  자연스럽게 끌어와 신뢰·흥미를 만든다. 각 항목 {{who, role}}. 없으면 빈 배열.
- storyline: 이야기를 어떻게 끌고 가는지 한 줄 흐름(기승전결 요약).
- development: 전개방식을 한 단어~짧게. 예: 시간순, 문제→해결, 개인일화형, 비교대조,
  실험/시연형, 반전폭로형, 리스트나열형.
- twist: 참신한 발상전환/반전 포인트(있으면 그 대목, 없으면 "").
- appeal: 어필포인트 — 시청자를 무엇으로 끌어당기나. 예: 돈 절약, 손실회피("이거 모르면 손해"),
  건강/안전, 편리함, 호기심 해소, 공감/위로, 과시.
- tone: 말투·어미 스타일 — 화자의 말투와 문장 끝(어미) 특징을 짧게. 예: "친근한 존댓말,
  ~거든요/~더라고요/~잖아요 수다체", "담백한 정보체, ~하세요/~합니다".
- beats: 시간 순서 '비트' 배열. 각 비트 label(훅|문제제기|공감|주변인물등장|반전|증거/시연|
  결과|CTA 등), desc(역할 한 줄), approx_sec("0-2").
- devices: 수사·설득 장치(권위자인용, 구체적숫자, 감정트리거, 비포애프터, 손실회피,
  시연, 반문 등). 해당되는 것만.
- target_seconds: 전체 길이 추정(초).
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
