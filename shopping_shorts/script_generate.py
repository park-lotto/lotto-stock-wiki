"""S급 대본의 구조를 빌려 새 20초 대본 초안 생성 — 유지/변형 토글 + 모드 A/B.

위키의 검증된 뼈대(주변인물·발상전환·전개방식·훅·어필포인트·말투)를 재료로,
사용자가 각 요소를 '유지/변형' 지정하면 그에 맞춰 Gemini가 여러 초안을 만든다.
- 모드 A: 원본과 같은 주제로 신선하게 변주.
- 모드 B: 구조만 빌려 사용자가 준 '내 주제/제품'에 이식.
전용 키풀(comment_gen) 재사용. 실패/무키면 [].
"""
import json
import random

from google.genai import types

from shopping_shorts import comment_gen
from pipeline.atoms import key_vault

_MODEL = comment_gen._MODEL

# produce 대본생성(제미니자동·우리믹스)은 comment_gen 전용키(1개, 쉽게 소진) 대신
# key_vault 공유풀을 캐스케이드로 쓴다 — 배치된 예비키(general→ingest→embed→briefing)를
# 전부 활용해 소진 사고를 피한다(2026-07-13).
_GEN_GROUP = "general"


def _generate_drafts(prompt):
    """key_vault 캐스케이드 키풀로 대본 초안 리스트 생성. 소진키는 마킹하고 다음 키로.
    무키·전부실패면 []."""
    keys = key_vault.get_live_keys_cascade(_GEN_GROUP)
    if not keys:
        return []
    for key in keys:
        try:
            resp = key_vault.get_client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            return json.loads(resp.text).get("drafts", [])
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                key_vault.mark_exhausted(key_vault._owner_group(key) or _GEN_GROUP, key)
                continue
            if key_vault.is_quota_error(e):
                continue  # 순간 rate limit — 다음 키로
            return []
    return []

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
    return _generate_drafts(prompt)


_MIX_PROMPT = """너는 한국 쇼핑 숏폼 대본 작가다. 아래 여러 개의 검증된 S급 대본이 있다.
각 대본의 **강점**(훅·전개방식·주변인물 활용·말투)을 뽑아 하나로 **조합**한, 약 {seconds}초
분량(대략 {words}단어)의 새 대본 초안 {n}개를 만들어라.

[재료 대본들]
{sources}

규칙:
- 특정 대본을 통째로 베끼지 말고, 각 대본의 좋은 부분을 골라 자연스럽게 녹여 새로 써라.
- 훅은 가장 강한 대본의 훅 방식을 살리고, 전개·주변인물·말투도 좋은 걸 조합해라.
- 실제로 읽을 구어체 나레이션(0초 훅 → … → 끝 CTA). 억지 설정·과장 금지.
- 초안끼리 서로 다르게 조합을 시도해라.
각 초안: hook(첫 훅 한 줄), script(전체 나레이션 대본), applied(어느 대본의 무엇을 조합했는지 한 줄).
JSON만 출력."""


def _mix_source_block(sources):
    lines = []
    for i, s in enumerate(sources, 1):
        st = s.get("structure") or {}
        chs = ", ".join(f"{c.get('who')}({c.get('role')})" for c in (st.get("characters") or [])) or "없음"
        lines.append(
            f"[대본 {i}] {s.get('name') or ''}\n"
            f"- 훅: {st.get('hook') or '(미상)'}\n"
            f"- 전개방식: {st.get('development') or '(미상)'}\n"
            f"- 주변인물: {chs}\n"
            f"- 말투/어미: {st.get('tone') or '(미상)'}\n"
            f"- 전체대본: {(s.get('full_text') or '')[:800]}")
    return "\n\n".join(lines)


def generate_mix(sources, target_seconds=20, n=3, max_key_tries=3):
    """여러 S급 대본(각 {name, full_text, structure})의 강점을 조합해 새 대본 초안 리스트.
    우리믹스(Feature B) 모드. 소스 2개 미만이거나 무키면 []."""
    sources = [s for s in (sources or []) if (s.get("full_text") or "").strip()]
    if not comment_gen.SHORTS_GEMINI_KEYS or len(sources) < 2:
        return []
    n = max(1, min(int(n or 3), 5))
    seconds = max(5, min(int(target_seconds or 20), 90))
    words = max(15, round(seconds * 2.3))
    prompt = _MIX_PROMPT.format(sources=_mix_source_block(sources[:3]), seconds=seconds, words=words, n=n)
    return _generate_drafts(prompt)


def _elem_lines(structure, elem_modes, category_lookup):
    """요소별 지시 라인 생성. elem_modes: {element_key: mode_string}, mode_string은
    "keep"(원본유지) / "free"(AI 자유즉흥) / "random"(학습된 카테고리 중 랜덤) /
    "category:<label>"(특정 카테고리 지정) 중 하나(2026-07-13, 4단 모드).
    category_lookup: {element: [{"label","description"}, ...]} — Store.get_element_options()
    형태. 지정/랜덤 모드인데 옵션이 없으면 free로 자동 폴백."""
    _STRUCT_KEY = {"hook": "hook_type"}  # analyze_structure 출력 필드명과 매핑
    lines = []
    for key, label in ELEM_LABELS.items():
        struct_key = _STRUCT_KEY.get(key, key)
        if key == "characters":
            chs = structure.get("characters") or []
            val = ", ".join(f"{c.get('who')}({c.get('role')})" for c in chs) or "없음"
        else:
            val = structure.get(struct_key) or "(원본에 없음)"

        mode = elem_modes.get(key, "keep")
        options = category_lookup.get(key) or []

        if mode == "keep":
            lines.append(f"- {label}: 유지 → 원본과 같은 강점 살려라 [{val}]")
            continue
        if mode == "random" and options:
            mode = "category:" + random.choice(options)["label"]
        if mode.startswith("category:") and options:
            wanted = mode.split(":", 1)[1]
            opt = next((o for o in options if o["label"] == wanted), None)
            if opt:
                lines.append(
                    f"- {label}: 반드시 '{opt['label']}' 유형으로 — {opt['description']} "
                    f"(원본[{val}]과 달라도 됨, 이 카테고리 안에서 자연스럽게)")
                continue
        # free 모드이거나, category/random인데 옵션이 없으면 자유즉흥으로 폴백
        lines.append(f"- {label}: 변형(자유 즉흥) → 원본[{val}]과 다르게 더 참신하게 바꿔라")
    return "\n".join(lines)


def generate_variations(structure, full_text, elem_modes, category_lookup, mode="A",
                         my_topic="", n=3, max_key_tries=3):
    """구조+대본을 재료로 요소별 모드 지시에 맞춰 초안 리스트 반환. 실패/무키면 []."""
    if not comment_gen.SHORTS_GEMINI_KEYS or not (full_text or "").strip():
        return []
    n = max(1, min(int(n or 3), 5))
    if mode == "B" and (my_topic or "").strip():
        topic_line = f"주제: 구조만 빌리고 아래 '내 주제/제품'에 맞춰 새로 써라.\n내 주제/제품: {my_topic.strip()}"
    else:
        topic_line = "주제: 원본과 같은 주제 영역에서, 내용은 새롭게 신선하게 변주"
    prompt = _GEN_PROMPT.format(
        full_text=full_text[:3000], elems=_elem_lines(structure or {}, elem_modes, category_lookup),
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


_REFINE_SCHEMA = {
    "type": "object",
    "properties": {"script": {"type": "string"}},
    "required": ["script"],
}

_REWRITE_PROMPT = """너는 한국 쇼핑 숏폼 대본 작가다. 아래 대본을 지시에 맞춰 통째로
다시 써라(구어체 나레이션, 0초 훅부터 끝 CTA까지 흐름은 유지).

[원본 대본]
{script}

[지시]
{instruction}

다음 JSON으로만 출력: {{"script": "다시 쓴 전체 대본"}}"""

_PARTIAL_PROMPT = """너는 한국 쇼핑 숏폼 대본 작가다. 아래 대본에서 지정된 부분만
지시대로 바꿔라. 지정된 부분 밖은 토씨 하나 그대로 유지해라.

[원본 대본 전체]
{script}

[바꿀 부분]
{selected}

[지시]
{instruction}

다음 JSON으로만 출력: {{"script": "수정된 전체 대본(바뀐 부분만 반영, 나머지는 원본 그대로)"}}"""


def _refine(prompt, max_key_tries=3):
    if not comment_gen.SHORTS_GEMINI_KEYS:
        return ""
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return ""
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_REFINE_SCHEMA),
            )
            return json.loads(resp.text).get("script", "")
        except Exception as e:  # noqa: BLE001 — 재생성 실패는 치명적 아님(빈 문자열)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            return ""
    return ""


def refine_draft_rewrite(script_text, instruction, max_key_tries=3):
    """대본 전체를 지시문에 맞춰 다시 쓴다. 실패/무키면 ""."""
    return _refine(_REWRITE_PROMPT.format(script=script_text, instruction=instruction), max_key_tries)


def refine_draft_partial(script_text, selected_text, instruction, max_key_tries=3):
    """선택한 부분만 지시문에 맞춰 바꾸고 나머지는 유지. 실패/무키면 ""."""
    return _refine(
        _PARTIAL_PROMPT.format(script=script_text, selected=selected_text, instruction=instruction),
        max_key_tries)
