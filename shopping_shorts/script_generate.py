"""S급 대본의 구조를 빌려 새 20초 대본 초안 생성 — 유지/변형 토글 + 모드 A/B.

위키의 검증된 뼈대(주변인물·발상전환·전개방식·훅·어필포인트·말투)를 재료로,
사용자가 각 요소를 '유지/변형' 지정하면 그에 맞춰 Gemini가 여러 초안을 만든다.
- 모드 A: 원본과 같은 주제로 신선하게 변주.
- 모드 B: 구조만 빌려 사용자가 준 '내 주제/제품'에 이식.
전용 키풀(comment_gen) 재사용. 실패/무키면 [].
"""
import json

from google.genai import types

from shopping_shorts import comment_gen

_MODEL = comment_gen._MODEL

# 유지/변형 토글 대상 요소(키 → 표시 라벨). 프론트·엔드포인트가 공유.
ELEM_LABELS = {
    "characters": "등장 주변인물",
    "twist": "발상전환",
    "development": "전개방식",
    "hook": "훅",
    "appeal": "어필포인트",
    "tone": "말투/어미",
}
ELEM_KEYS = list(ELEM_LABELS)

_SCHEMA = {
    "type": "object",
    "properties": {
        "drafts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string"},
                    "script": {"type": "string"},
                    "applied": {"type": "string"},
                },
                "required": ["hook", "script", "applied"],
            },
        }
    },
    "required": ["drafts"],
}

_GEN_PROMPT = """너는 한국 쇼핑 숏폼(살림·요리·인테리어) 대본 작가다. 아래 'S급 원본 대본'의
검증된 구조를 빌려, 20초 분량(약 45~70단어)의 새 대본 초안 {n}개를 만들어라.

[S급 원본 대본]
{full_text}

[구조 요소별 지시 — 유지/변형]
{elems}

[{topic_line}]

규칙:
- 각 초안은 실제로 읽을 나레이션(구어체). 0초 훅부터 끝 CTA까지 이어지게.
- '변형' 요소는 원본을 베끼지 말고 참신하게 바꾸고, '유지' 요소는 그 강점을 그대로 살려라.
- 주변인물을 쓸 땐 오버하지 말고 자연스럽게(예: "농원 하는 언니가", "김밥집 사장님이",
  "병원 하는 지인이"). 억지 설정·과장 금지.
- 초안끼리 서로 다르게(훅·전개를 다양하게 시도).
각 초안: hook(첫 훅 한 줄), script(전체 나레이션 대본), applied(무엇을 유지/변형했는지 한 줄).
JSON만 출력."""


_TOPIC_PROMPT = """너는 한국 쇼핑 숏폼(살림·요리·인테리어·생활용품) 대본 작가다.
아래 주제/제품으로 약 {seconds}초 분량(대략 {words}단어)의 판매용 숏폼 나레이션
대본 초안 {n}개를 새로 써라.

[주제/제품]
{topic}

규칙:
- 실제로 읽을 구어체 나레이션. 0초 훅 → 문제공감 → 반전/해결 → 실사용 → 끝 CTA 흐름.
- 훅은 첫 1초에 시선을 잡게(궁금증·반전·공감 중 하나). 광고티 과하지 않게 자연스럽게.
- 초안끼리 훅·전개를 서로 다르게 시도해라.
각 초안: hook(첫 훅 한 줄), script(전체 나레이션 대본), applied(어떤 각도로 썼는지 한 줄).
JSON만 출력."""


def generate_from_topic(topic, target_seconds=20, n=3, max_key_tries=3):
    """주제/제품 하나로 처음부터 대본 초안 리스트 생성(제미니 자동 모드). 실패/무키면 [].

    generate_variations(원본 필요=Feature A)와 달리 소스 대본 없이 주제만으로 만든다.
    한국어 대략 6.5자/초 기준으로 목표 길이에 맞춰 분량을 지시한다."""
    if not comment_gen.SHORTS_GEMINI_KEYS or not (topic or "").strip():
        return []
    n = max(1, min(int(n or 3), 5))
    seconds = max(5, min(int(target_seconds or 20), 90))
    words = max(15, round(seconds * 2.3))  # 대략치(초당 ~2.3단어)
    prompt = _TOPIC_PROMPT.format(topic=topic.strip()[:1000], seconds=seconds, words=words, n=n)
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return []
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            return json.loads(resp.text).get("drafts", [])
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님(빈 리스트)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            return []
    return []


def _elem_lines(structure, keep_flags):
    lines = []
    for key, label in ELEM_LABELS.items():
        if key == "characters":
            chs = structure.get("characters") or []
            val = ", ".join(f"{c.get('who')}({c.get('role')})" for c in chs) or "없음"
        else:
            val = structure.get(key) or "(원본에 없음)"
        if keep_flags.get(key, True):
            lines.append(f"- {label}: 유지 → 원본과 같은 강점 살려라 [{val}]")
        else:
            lines.append(f"- {label}: 변형 → 원본[{val}]과 다르게 더 참신하게 바꿔라")
    return "\n".join(lines)


def generate_variations(structure, full_text, keep_flags, mode="A", my_topic="", n=3, max_key_tries=3):
    """구조+대본을 재료로 유지/변형 지시에 맞춰 초안 리스트 반환. 실패/무키면 []."""
    if not comment_gen.SHORTS_GEMINI_KEYS or not (full_text or "").strip():
        return []
    n = max(1, min(int(n or 3), 5))
    if mode == "B" and (my_topic or "").strip():
        topic_line = f"주제: 구조만 빌리고 아래 '내 주제/제품'에 맞춰 새로 써라.\n내 주제/제품: {my_topic.strip()}"
    else:
        topic_line = "주제: 원본과 같은 주제 영역에서, 내용은 새롭게 신선하게 변주"
    prompt = _GEN_PROMPT.format(
        full_text=full_text[:3000], elems=_elem_lines(structure or {}, keep_flags),
        topic_line=topic_line, n=n)
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return []
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            return json.loads(resp.text).get("drafts", [])
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님(빈 리스트)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            return []
    return []
