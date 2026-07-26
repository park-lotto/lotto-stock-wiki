"""생성 프롬프트 주입용 은행 컨텍스트 조립(Phase2 토대). store 읽기만, Gemini 없음.
★중괄호 소독 필수 — script_generate 프롬프트가 .format()을 돌린다(_STORY_RULES_CORE 옆에 낀다)."""
import random

from shopping_shorts.pattern_bank import STYLE_BUCKETS, CONTENT_BUCKETS

_LABEL = {"hook": "훅", "ending": "마무리", "adverb": "담화부사", "cta": "CTA", "price": "가격표현"}

# 로테이션 창: 상위 perf 풀(=max(k*_POOL_MULT, _POOL_MIN))에서 k개를 매 호출 랜덤 샘플.
# top-k 고정이면 매 영상이 같은 훅으로 열려 단조롭다(P0-1) — 잘된 것 위주(풀=perf 상위)로
# 하되 그 안에서 무작위라 job마다 다른 조합이 나온다. 풀보다 승인이 적으면 전부 쓴다.
# ★2026-07-23 풀 대폭 확대(사장님: "은행에 훅 수백갠데 매번 같다"): 상위 40으로 넓혀
# 승인 200+개가 실제로 로테이션되게 한다(perf 피드백 없어 상위20은 사실상 고정집합이었다).
_POOL_MULT = 8
_POOL_MIN = 40


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


_STRONG_HOOK_STARTS = ("와", "헐", "아니", "이거", "이걸", "저 이거", "제가", "여러분")
_STRONG_HOOK_WORDS = ("대박", "충격", "진짜", "절대", "왜", "몰랐", "후회", "천재", "꿀", "이제 알", "이런 게")


def _hook_strength(text):
    """훅 강도 휴리스틱(2026-07-23 사장님: "훅이 약해, 제일 강한 걸 우선"). 은행에 engagement
    실측이 없어(perf 대부분 0) 텍스트 신호로 강한 훅을 앞세운다: 강한 오프너로 시작·물음표·
    감탄·충격/발견 어휘·이모지 = 가점 / 길고 설명체 = 감점."""
    t = (text or "").strip()
    if not t:
        return -99
    s = 0
    if t.startswith(_STRONG_HOOK_STARTS):
        s += 3
    if "?" in t:
        s += 2
    if "!" in t:
        s += 1
    s += sum(1 for w in _STRONG_HOOK_WORDS if w in t)
    if any(e in t for e in ("😱", "🚨", "🔥", "😳", "❗", "🤫")):
        s += 1
    if len(t) > 45:          # 너무 긴 설명체 훅 감점
        s -= 2
    return s


def _sample_bucket(store, bucket, k, rng=random, rank_key=None):
    """승인 부품 상위 perf 풀에서 k개 랜덤 샘플(로테이션). 승인이 k 이하면 전부.
    rank_key 주면(훅 강도 등) 넉넉히 뽑아 **강도 상위**에서만 로테이션 → 강한 것 우선+매번 다르게."""
    limit = max(k * _POOL_MULT, _POOL_MIN)
    if rank_key:
        limit = max(limit, k * 10)   # 강도 랭킹용으로 넉넉히
    pool = store.list_pattern_items(bucket=bucket, status="approved", order_by="perf", limit=limit)
    if rank_key and len(pool) > k:
        pool = sorted(pool, key=lambda it: rank_key(it.get("text", "")), reverse=True)[:max(k * 2, 12)]
    if len(pool) <= k:
        return pool
    return rng.sample(pool, k)


def parts_block(store, k=5, rng=random):
    """STYLE_BUCKETS별 승인부품 k개(상위 perf 풀에서 로테이션 샘플) → 프롬프트 블록. 부품 없으면 ''."""
    lines = []
    for b in STYLE_BUCKETS:
        # 훅은 강도 상위에서만 로테이션(약한 설명체 훅 배제) — 사장님 "제일 강한 훅 우선".
        items = _sample_bucket(store, b, k, rng=rng, rank_key=_hook_strength if b == "hook" else None)
        if not items:
            continue
        texts = ", ".join(_sanitize(it["text"]) for it in items)
        lines.append(f"· {_LABEL.get(b, b)}: {texts}")
    if not lines:
        return ""
    return ("[승인된 부품 — 이 결·패턴을 살려 써라. ★훅은 초반 3초가 승부처다. 후보 3개의 "
            "훅을 아래 3가지로 '서로 다르게' 만들어라(같은 틀 복제 금지):\n"
            "  ① 벤치마킹형 — 위 승인훅이 '왜 통했는지'(호기심·경고·반전 등 심리 트리거)만 "
            "가져와 우리 소재로 새로 써라. 문장을 그대로 베끼지 마라.\n"
            "  ② 트렌드·반전형 — 이 카테고리의 지금 유행 어조를 반영해라(예: '다이소 가면 이건 "
            "꼭 사와' 뿐 아니라 '이건 진짜 사지마' 같은 반전형도). 뻔한 정공법 대신 반전·금기로 열어라.\n"
            "  ③ 신선·임팩트형 — 은행에 얽매이지 말고 3초 안에 스크롤을 멈출 가장 강한 훅을 "
            "자유롭게 창작해라.\n"
            "CTA·나머지 부품은 구조·리듬만 가져오고 단어·인물·소재는 우리 것으로. "
            "인명·상표·지명 등 고유명사는 반드시 교체(표절·중복 회피).]\n"
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
