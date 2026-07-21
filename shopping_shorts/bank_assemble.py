"""생성 프롬프트 주입용 은행 컨텍스트 조립(Phase2 토대). store 읽기만, Gemini 없음.
★중괄호 소독 필수 — script_generate 프롬프트가 .format()을 돌린다(_STORY_RULES_CORE 옆에 낀다)."""
from shopping_shorts.pattern_bank import STYLE_BUCKETS

_LABEL = {"hook": "훅", "ending": "마무리", "adverb": "담화부사", "cta": "CTA", "price": "가격표현"}


def _sanitize(text):
    """format() 안전 — { } → ( ). 주입 문자열은 반드시 통과시킬 것."""
    return (text or "").replace("{", "(").replace("}", ")")


def spine_charter(spine):
    """승인 스파인 dict → 이야기 골격 서술문(중괄호 소독). None/빈 dict → ''."""
    if not spine:
        return ""
    parts = []
    if spine.get("situation_type"):
        parts.append(f"상황={_sanitize(spine['situation_type'])}")
    if spine.get("emotion_arc"):
        parts.append(f"감정선={_sanitize(spine['emotion_arc'])}")
    head = "★학습된 아크(이 이야기 골격을 따르라): " + " · ".join(parts) if parts else ""
    bc = spine.get("beat_chain") or []
    if bc:
        chain = " → ".join(_sanitize(b) for b in bc)
        head = (head + f"\n  비트: {chain}") if head else f"★학습된 아크 비트: {chain}"
    return head


def parts_block(store, k=5):
    """STYLE_BUCKETS별 승인부품 top-k(perf) → 프롬프트 블록. 부품 없으면 ''."""
    lines = []
    for b in STYLE_BUCKETS:
        items = store.list_pattern_items(bucket=b, status="approved", order_by="perf", limit=k)
        if not items:
            continue
        texts = ", ".join(_sanitize(it["text"]) for it in items)
        lines.append(f"· {_LABEL.get(b, b)}: {texts}")
    if not lines:
        return ""
    return ("[승인된 부품 — 이 결·패턴을 참고해 새로 써라. ★그대로 베끼기 금지: 특히 훅·CTA는 "
            "구조와 리듬만 가져오고 단어·인물·소재는 반드시 우리 것으로 바꿔라(표절·중복 회피).]\n"
            + "\n".join(lines))


def assemble_bank_context(store, category, k=5):
    """스파인 charter + 부품 top-k 합본. 둘 다 없으면 ''(호출부는 빈 문자열이면
    기존 헌장만 써서 회귀0)."""
    spine = store.pick_spine_for_category(category) if category else None
    blocks = [x for x in (spine_charter(spine), parts_block(store, k)) if x]
    return "\n\n".join(blocks)
