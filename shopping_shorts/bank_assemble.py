"""생성 프롬프트 주입용 은행 컨텍스트 조립(Phase2 토대). store 읽기만, Gemini 없음.
★중괄호 소독 필수 — script_generate 프롬프트가 .format()을 돌린다(_STORY_RULES_CORE 옆에 낀다)."""
import random

from shopping_shorts.pattern_bank import STYLE_BUCKETS, CONTENT_BUCKETS

_LABEL = {"hook": "훅", "ending": "마무리", "adverb": "담화부사", "cta": "CTA", "price": "가격표현"}

# 로테이션 창: 상위 perf 풀(=max(k*_POOL_MULT, _POOL_MIN))에서 k개를 매 호출 랜덤 샘플.
# top-k 고정이면 매 영상이 같은 훅으로 열려 단조롭다(P0-1) — 잘된 것 위주(풀=perf 상위)로
# 하되 그 안에서 무작위라 job마다 다른 조합이 나온다. 풀보다 승인이 적으면 전부 쓴다.
_POOL_MULT = 4
_POOL_MIN = 12


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


def _sample_bucket(store, bucket, k, rng=random):
    """승인 부품 상위 perf 풀에서 k개 랜덤 샘플(로테이션). 풀=상위 max(k*_POOL_MULT,_POOL_MIN)개,
    승인이 k 이하면 전부. perf 상위를 풀로 쓰되 그 안에서 무작위 → 잘된 것 위주로 매번 다르게."""
    pool = store.list_pattern_items(bucket=bucket, status="approved", order_by="perf",
                                    limit=max(k * _POOL_MULT, _POOL_MIN))
    if len(pool) <= k:
        return pool
    return rng.sample(pool, k)


def parts_block(store, k=5, rng=random):
    """STYLE_BUCKETS별 승인부품 k개(상위 perf 풀에서 로테이션 샘플) → 프롬프트 블록. 부품 없으면 ''."""
    lines = []
    for b in STYLE_BUCKETS:
        items = _sample_bucket(store, b, k, rng=rng)
        if not items:
            continue
        texts = ", ".join(_sanitize(it["text"]) for it in items)
        lines.append(f"· {_LABEL.get(b, b)}: {texts}")
    if not lines:
        return ""
    return ("[승인된 부품 — 이 결·패턴을 참고해 새로 써라. ★그대로 베끼기 금지: 특히 훅·CTA는 "
            "구조와 리듬만 가져오고 단어·인물·소재는 반드시 우리 것으로 바꿔라(표절·중복 회피).]\n"
            + "\n".join(lines))


_CONTENT_LABEL = {"evidence": "근거 대는 법", "conflict": "갈등·문제 설정", "emotion": "감정 반응"}


def content_block(store, k=4, rng=random):
    """내용 버킷(근거·갈등·감정) 승인 템플릿 → '전개 패턴' 블록(2026-07-23). 우승작에서 뽑은
    '{인물}이 {행위}하니 {결과}' 슬롯 템플릿이라, 생성이 표면 말투를 넘어 **이야기 전개**를
    검증된 패턴으로 깊게 쓰게 한다. 템플릿 없으면 ''(회귀0)."""
    lines = []
    for b in CONTENT_BUCKETS:
        items = _sample_bucket(store, b, k, rng=rng)
        if not items:
            continue
        texts = " / ".join(_sanitize(it["text"]) for it in items)
        lines.append(f"· {_CONTENT_LABEL.get(b, b)}: {texts}")
    if not lines:
        return ""
    return ("[학습된 전개 패턴 — 우승작에서 뽑은 이야기 전개 틀. ★이 {슬롯} 구조로 스토리를 "
            "'깊게' 전개하되(근거·갈등·감정), 슬롯은 우리 소재·인물로 채워라. 리터럴 베끼기 금지.]\n"
            + "\n".join(lines))


def avoid_block(store, limit=6):
    """novelty(P0-3): 최근 영상이 쓴 훅·인물·CTA를 '이건 이미 썼으니 다르게 써라'로 블록화.
    이력 없으면 ''. 중괄호 소독(생성 프롬프트가 .format()을 탄다)."""
    rec = store.recent_script_usage(limit=limit)
    parts = []
    if rec["hooks"]:
        parts.append("· 훅: " + " / ".join(_sanitize(h) for h in rec["hooks"]))
    if rec["persons"]:
        parts.append("· 인물: " + ", ".join(_sanitize(p) for p in rec["persons"]))
    if rec["ctas"]:
        parts.append("· CTA: " + ", ".join(_sanitize(c) for c in rec["ctas"]))
    if not parts:
        return ""
    return ("[최근 영상에서 이미 쓴 것 — ★반드시 다르게 써라(같은 훅·인물·CTA 반복 금지, "
            "매 영상이 똑같이 열리면 안 된다)]\n" + "\n".join(parts))


def assemble_bank_context(store, category, k=5):
    """스파인 charter + 부품 top-k 합본. 둘 다 없으면 ''(호출부는 빈 문자열이면
    기존 헌장만 써서 회귀0)."""
    # ★category 비어도(자동유형 경로는 video_type=None→"") 스파인을 건너뛰지 마라(2026-07-23
    # 실측 버그: `if category`가 falsy라 pick을 아예 안 불러 승인 스파인 4개가 죽어 있었다).
    # pick_spine_for_category(None)은 fit_categories 없는 범용 스파인을 perf 최고로 반환한다.
    spine = store.pick_spine_for_category(category or None)
    # 스파인(아크) + 말투(parts_block) + ★전개 패턴(content_block, 2026-07-23) 3층 주입.
    blocks = [x for x in (spine_charter(spine), parts_block(store, k), content_block(store)) if x]
    return "\n\n".join(blocks)


def bank_usage_snapshot(store, category, k=5):
    """생성 프롬프트에 은행이 무엇을 주입했나 — 계측 dict(읽기만, Gemini 없음).
    empty=True면 스파인·부품 통째로 비어 bank_context가 '' = 은행 무용."""
    enabled = store.get_setting("bank_enabled", "") == "1"
    spine = store.pick_spine_for_category(category or None)   # 빈 category=범용(위 assemble와 동일)
    spine_beats = len((spine or {}).get("beat_chain") or []) if spine else 0
    parts_by_bucket = {}
    for b in STYLE_BUCKETS:
        pool = store.list_pattern_items(bucket=b, status="approved", order_by="perf",
                                        limit=max(k * _POOL_MULT, _POOL_MIN))
        n = min(len(pool), k)
        if n:
            parts_by_bucket[b] = n
    parts_total = sum(parts_by_bucket.values())
    rec = store.recent_script_usage()
    avoid_present = bool(rec.get("hooks") or rec.get("persons") or rec.get("ctas"))
    return {
        "bank_enabled": enabled,
        "spine_present": bool(spine),
        "spine_beats": spine_beats,
        "parts_by_bucket": parts_by_bucket,
        "parts_total": parts_total,
        "avoid_present": avoid_present,
        "category": category or "",
        "empty": (not spine) and parts_total == 0,
    }
