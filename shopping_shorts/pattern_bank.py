"""부품은행 8버킷 추출 모듈(2026-07-21, Phase0 T2).

S급 대본을 Gemini로 8버킷 부품으로 분해한다:
 · 스타일 버킷(hook/ending/adverb/cta/price) = **리터럴 문구** 리스트.
   문구 그대로 담아 재사용한다(훅·어미·담화부사·CTA·가격표현).
 · 내용 버킷(evidence/conflict/emotion) = **슬롯 템플릿** 문자열
   (예: "{인물}이 {행위}하더니 {반응}"). 리터럴을 담으면 남의 사연을 베끼는 꼴이라
   인물/행위/반응을 슬롯으로 추상화해 담는다(slot_role='template').
 · spine = 매크로 스파인 후보(상황유형·비트체인·감정아크·어필).

structure_analyze 패턴을 따른다: comment_gen 전용 키풀 로테이션 + response_schema,
실패/무키 시 {}. 테스트는 call 주입점으로 실제 Gemini 호출을 회피한다
(call(prompt, schema) -> dict|None; edit_plan.build_scene_first_plan의 call 패턴).
"""
import json
import sys

from google.genai import types

from shopping_shorts import comment_gen
from shopping_shorts.store import PATTERN_BUCKETS

_MODEL = comment_gen._MODEL

# 스타일=리터럴, 내용=슬롯템플릿. store.PATTERN_BUCKETS를 이 둘로 가른다.
STYLE_BUCKETS = ("hook", "ending", "adverb", "cta", "price")
CONTENT_BUCKETS = ("evidence", "conflict", "emotion")

_STR_ARRAY = {"type": "array", "items": {"type": "string"}}

_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "hook": _STR_ARRAY,
        "ending": _STR_ARRAY,
        "adverb": _STR_ARRAY,
        "cta": _STR_ARRAY,
        "price": _STR_ARRAY,
        "evidence": _STR_ARRAY,
        "conflict": _STR_ARRAY,
        "emotion": _STR_ARRAY,
        "spine": {
            "type": "object",
            "properties": {
                "situation_type": {"type": "string"},
                "beat_chain": {"type": "array", "items": {"type": "string"}},
                "emotion_arc": {"type": "string"},
                "appeal": {"type": "string"},
            },
        },
    },
    "required": list(PATTERN_BUCKETS),
}

_PROMPT = """너는 바이럴 숏폼 대본을 '재사용 가능한 부품'으로 해부하는 분석가다.
아래 대본을 8개 버킷으로 분해하라. ★스타일 부품은 문구를 그대로 뽑고, 내용 부품은
인물/행위/반응을 슬롯으로 추상화하라(남의 사연을 베끼지 않기 위함).

[대본 전체]
{full_text}

버킷:
- hook: 첫 훅(관심을 끄는 도입) 문구들. **문구 그대로**.
- ending: 특징적인 문장 끝(어미) 표현들. 예: "~하더라고요", "~거든요". **문구 그대로**.
- adverb: 담화부사·강조어. 예: "진짜", "완전", "솔직히". **문구 그대로**.
- cta: 마무리 행동유도 문구. 예: "댓글로 알려주세요", "저장해두세요". **문구 그대로**.
- price: 가격·비용 표현. 예: "단돈 5천원", "반값에". **문구 그대로**.
- evidence: 증거·근거를 제시하는 대목을 **슬롯 템플릿**으로. 예: "{인물}이 {행위}하니 {결과}".
- conflict: 갈등·문제 상황을 **슬롯 템플릿**으로. 예: "{인물}이 {문제}로 곤란해하다".
- emotion: 감정 반응을 **슬롯 템플릿**으로. 예: "{인물}이 {반응}하며 놀라다".
- spine: 이 대본의 매크로 뼈대 — situation_type(상황유형 한 단어), beat_chain(비트 순서 배열),
  emotion_arc("불안→안도" 형태), appeal(무엇으로 끌어당기나).

각 버킷은 해당되는 항목만(없으면 빈 배열). 내용 버킷(evidence/conflict/emotion)에는
반드시 {슬롯} 형태를 써서 리터럴 사연을 그대로 담지 마라. JSON만 출력."""


def _vault_fallback(prompt, schema, max_tries=4):
    """전용 SHORTS 키풀이 비었을 때 key_vault 예비키풀(general)로 폴백. edit_plan._vault_call과 동일 경로.
    서버에 SHORTS_GEMINI_KEYS 미설정이어도 부품은행 추출이 도는 핵심 수정."""
    kv = comment_gen.key_vault
    keys = kv.get_live_keys_cascade("general")
    if not keys:
        return None
    for key in keys[:max_tries]:
        try:
            resp = kv.get_client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=schema),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001
            if kv.is_daily_exhausted_error(e) or kv.is_account_disabled_error(e):
                kv.mark_exhausted(kv._owner_group(key) or "general", key)
                continue
            if kv.is_quota_error(e):
                continue
            print(f"pattern_bank._vault_fallback: {e!r}", file=sys.stderr)
            return None
    return None


def _default_call(prompt, schema, max_key_tries=3):
    """comment_gen 전용 키풀 로테이션으로 JSON 생성(structure_analyze 방식).
    전용 풀이 비었으면 key_vault 예비풀로 폴백. 무키/실패면 None."""
    if not comment_gen.SHORTS_GEMINI_KEYS:
        return _vault_fallback(prompt, schema)
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return None
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=schema),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 — 추출 실패는 치명적 아님(빈 dict로 처리)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            print(f"pattern_bank._default_call: {e!r}", file=sys.stderr)
            return None
    return None


def extract_buckets(full_text, call=None):
    """대본 → 8버킷 dict(+spine). 무키/실패/빈 텍스트면 {}.

    반환 예: {"hook": [...], "ending": [...], ..., "spine": {...}}.
    call(prompt, schema)->dict를 주입하면 그걸로(테스트), 없으면 실제 Gemini."""
    if not (full_text or "").strip():
        return {}
    _call = call or _default_call
    # .format 금지 — 프롬프트에 {인물}·{슬롯} 리터럴 중괄호가 많다. 토큰만 치환.
    prompt = _PROMPT.replace("{full_text}", full_text[:4000])
    raw = _call(prompt, _EXTRACT_SCHEMA)
    if not raw or not isinstance(raw, dict):
        return {}
    return raw


def ingest_script(store, full_text, source="manual", url="",
                  product_category=None, category_source=None, perf=None, call=None):
    """대본을 분해해 부품은행에 담는다 → {source_id, added}.

    extract_buckets → add_pattern_source(원본 1건) → 각 부품 add_pattern_item(pending).
    스타일 버킷은 리터럴, 내용 버킷은 slot_role='template'. 추출 실패 시
    {source_id: None, added: 0}(소스도 안 만든다 — 빈 소스 유령 방지).
    perf/category_source는 자동크롤 결합(Phase1)에서 넘어온다(R3·R4)."""
    buckets = extract_buckets(full_text, call=call)
    if not buckets:
        return {"source_id": None, "added": 0}
    source_id = store.add_pattern_source(
        source, url, full_text, product_category=product_category,
        category_source=category_source, perf=perf, structure=buckets)
    added = 0
    for bucket in STYLE_BUCKETS:
        for text in buckets.get(bucket) or []:
            if not (text or "").strip():
                continue
            store.add_pattern_item(bucket, text, source_id=source_id)
            added += 1
    for bucket in CONTENT_BUCKETS:
        for text in buckets.get(bucket) or []:
            if not (text or "").strip():
                continue
            store.add_pattern_item(bucket, text, slot_role="template", source_id=source_id)
            added += 1
    return {"source_id": source_id, "added": added}


def ingest_negative(store, text, bucket):
    """반려문(쓰지 말 것)을 is_negative=1로 저장 → item id(F5).

    시드 예: cta '확인하셨어요', emotion '너무 좋아합니다'(요약체). 일반 목록
    (is_negative=0)에 안 뜨고, 생성 단계에서 '피해야 할 부품' 필터로 쓴다."""
    return store.add_pattern_item(bucket, text, is_negative=1)
