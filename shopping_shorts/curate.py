"""부품은행 AI 검수 — 자동승인된 부품 중 잡표현을 Gemini 판정으로 기각(오푸스 기준).
스타일 부품은 코드가 일괄 승인하지만, 밋밋한 설명체 훅 등 품질 낮은 건 여기서 걸러낸다.
배치 판정(부품 여러 개 한 콜)으로 비용 절감. 판정 누락은 유지(억울한 삭제 방지)."""
import sys

from shopping_shorts import pattern_bank

# 버킷별 검수 기준(오푸스 판단 rubric).
_CRITERIA = {
    "hook": (
        "첫 1초에 시청자를 붙잡는 '강한 훅'만 keep. "
        "궁금증·긴장·반전·강한 주장(절대~마세요)·구체적 인물/상황('시부모님 오셔서','딸이')·"
        "놀라운 결과가 있으면 keep. "
        "반대로 '여러분 ~는 이렇게 드세요/하세요'식 밋밋한 일반 설명·명령·인사·뻔한 문구는 reject."),
    "cta": (
        "행동유도로 자연스럽고 궁금증과 이어지는 CTA만 keep. "
        "밋밋하거나 뜬금없거나 문장이 안 되는 건 reject."),
    "ending": "실제 서울 구어체 종결어미로 자연스러우면 keep. 문어체·어색·잘린 조각은 reject.",
    "adverb": "대화에 생기를 주는 담화부사면 keep. 무의미하거나 부사가 아니면 reject.",
    "price": "가격/수량 표현으로 쓸모 있으면 keep. 아니면 reject.",
}

_SCHEMA = {
    "type": "object",
    "properties": {"verdicts": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "keep": {"type": "boolean"}},
        "required": ["id", "keep"]}}},
    "required": ["verdicts"],
}


def judge_parts(items, bucket, call=None):
    """부품 목록 → {id: keep_bool}. 판정에 없는 id는 결과에서 빠짐(호출부가 유지).
    call None/실패/무기준이면 {}(아무것도 기각 안 함 = 안전)."""
    if not items:
        return {}
    if call is None:
        call = pattern_bank._default_call
    crit = _CRITERIA.get(bucket)
    if not crit:
        return {}
    lines = "\n".join(f"  {it['id']}. {it.get('text', '')}" for it in items)
    prompt = (
        f"너는 한국 쇼핑 숏폼 대본 품질 심사관이다. 아래 '{bucket}' 부품들을 기준으로 심사해 "
        f"쓸 만한 것만 keep=true, 잡표현은 keep=false로 판정하라.\n"
        f"[기준]\n{crit}\n\n[부품들]\n{lines}\n\n"
        "각 부품의 id와 keep을 verdicts 배열 JSON으로만 출력.")
    res = call(prompt, _SCHEMA)
    if not res or not isinstance(res, dict):
        return {}
    out = {}
    for v in res.get("verdicts", []):
        if isinstance(v.get("id"), int) and isinstance(v.get("keep"), bool):
            out[v["id"]] = v["keep"]
    return out


def curate_bucket(store, bucket, batch=25, call=None):
    """은행의 approved '{bucket}' 부품을 배치로 심사 → 기각된 건 status='rejected'.
    반환=(심사수, 기각수). 내용 버킷(evidence/conflict/emotion)은 사람 몫이라 제외."""
    items = [{"id": i["id"], "text": i["text"]}
             for i in store.list_pattern_items(bucket=bucket, status="approved", limit=100000)]
    judged = rejected = 0
    for k in range(0, len(items), batch):
        chunk = items[k:k + batch]
        verdicts = judge_parts(chunk, bucket, call=call)
        for iid, keep in verdicts.items():
            judged += 1
            if not keep:
                try:
                    store.set_pattern_item_status(iid, "rejected")
                    rejected += 1
                except Exception as e:  # noqa: BLE001
                    print(f"curate reject 실패 {iid}: {e}", file=sys.stderr)
    return judged, rejected
