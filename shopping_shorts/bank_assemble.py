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
        # ★CTA는 은행에서 뽑지 않는다(2026-08-03 사장님 지시: "CTA는 고정으로 댓글에 OO
        #   남겨주세요로"). 은행에는 남의 채널에서 수확한 '프로필 👉 @아이디' 계열이 섞여
        #   있어서, 모델이 그걸 골라 **우리에게 없는 유입 경로**를 안내했다
        #   (실측 job 23208dec38e6: "비결 궁금하시면 프로필 링크 확인해주세요").
        #   댓글 유도는 우리 채널의 고정 전략이므로 형식을 아래에서 못박는다.
        if b == "cta":
            continue
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
            "나머지 부품은 구조·리듬만 가져오고 단어·인물·소재는 우리 것으로. "
            "인명·상표·지명 등 고유명사는 반드시 교체(표절·중복 회피).\n"
            "★CTA(마지막 비트)는 **반드시 \"댓글에 '{키워드}' 남겨주세요\" 형식**으로 써라 — "
            "키워드는 그 소재에 맞는 한 단어로 정해라(예: '신발'·'필름'·'점토').\n"
            "  프로필 링크·바로가기·아이디 안내 등 **다른 유입 경로는 절대 쓰지 마라**"
            "(우리에겐 그 경로가 없다).]\n"
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
    """novelty(P0-3): 최근 영상이 쓴 훅·인물을 '이건 이미 썼으니 다르게 써라'로 블록화.
    이력 없으면 ''. 중괄호 소독(생성 프롬프트가 .format()을 탄다).
    ★CTA는 2026-08-03부터 형식 고정이라 이 목록에서 뺐다(아래 주석 참조)."""
    rec = store.recent_script_usage(limit=limit)
    parts = []
    if rec["hooks"]:
        parts.append("· 훅: " + " / ".join(_sanitize(h) for h in rec["hooks"]))
    if rec["persons"]:
        parts.append("· 인물: " + ", ".join(_sanitize(p) for p in rec["persons"]))
    # ★CTA는 "다르게 써라" 대상에서 뺀다(2026-08-03). CTA 형식을 "댓글에 '{키워드}'
    #   남겨주세요"로 고정했는데(parts_block), 여기서 "최근 쓴 CTA와 다르게"를 요구하면
    #   서로 충돌해 모델이 형식을 벗어난다. 달라져야 하는 건 **키워드**지 형식이 아니다.
    if not parts:
        return ""
    return ("[최근 영상에서 이미 쓴 것 — ★반드시 다르게 써라(같은 훅·인물·CTA 반복 금지, "
            "매 영상이 똑같이 열리면 안 된다)]\n" + "\n".join(parts))


def _source_views(src):
    """pattern_source row의 perf에서 조회수(없으면 0). list_pattern_sources는 perf를 이미 디코드해 준다."""
    perf = src.get("perf") or {}
    try:
        return int(perf.get("views") or 0)
    except (TypeError, ValueError):
        return 0


def winners_block(store, category, k=2, max_chars=420):
    """검증된 우승 대본을 few-shot 예시로(2026-07-26). 스파인은 '뼈대'만 주는데, 여기에
    실제 조회수 높았던 원본 대본 전문을 통째로 보여줘 Gemini가 말투·호흡·디테일까지 흉내내게
    한다. ★같은 카테고리 우승작만 쓴다(2026-07-26 사고: 부족분을 타 카테고리로 채웠더니
    레시피 우승작의 '청양고추' 훅 소재가 홈템 영상에 새어들어 훅-본문이 따로 노는 C안이 나왔다).
    카테고리 매칭 우승작이 없으면 아예 안 준다(''=회귀0, 오염보다 무주입이 낫다)."""
    if not category:
        return ""   # 카테고리 불명이면 타 카테고리 오염 위험 → 무주입
    try:
        srcs = store.list_pattern_sources(limit=1000)
    except Exception:
        return ""
    same = [s for s in srcs
            if s.get("product_category") == category
            and len((s.get("full_text") or "").strip()) >= 40]
    if not same:
        return ""
    same.sort(key=_source_views, reverse=True)
    picked = same[:k]
    lines = []
    for i, s in enumerate(picked, 1):
        t = _sanitize(s.get("full_text", "").strip())
        if len(t) > max_chars:
            t = t[:max_chars] + "…"
        v = _source_views(s)
        vtxt = f"(조회수 {v:,})" if v else ""
        lines.append(f"[우승 예시 {i} {vtxt}]\n{t}")
    return ("[★검증된 우승 대본 — 이 카테고리에서 실제로 터진 대본 전문이다. 뼈대(스파인)를 "
            "지키되, 아래 예시의 '말투·호흡·구어체 리듬·감정선'만 배워서 그 느낌으로 써라.\n"
            "  ⚠️절대 규칙: 예시의 **소재·소품·제품명·특정 단어(예: 특정 식재료·브랜드)는 "
            "절대 가져오지 마라**. 오직 우리 영상의 소재로만 써라 — 예시가 '청양고추' 얘기여도 "
            "우리 영상이 주방 가림막이면 청양고추는 한 글자도 넣지 마라. 훅의 '강도와 리듬'만 "
            "흡수하고 소재는 100% 우리 것.]\n"
            + "\n\n".join(lines))


def style_block(style, seconds=30):
    """★스타일(스파인+beat_roles) → **칸을 못 박는** 프롬프트 블록(2026-08-15).

    `spine_charter`와 다른 점이 핵심이다. charter는 "이 골격을 따르라"는 **권유**라 AI가
    매번 새로 구성했다. 여기는 칸 이름(role)을 출력에 그대로 돌려받아 `script_gate`가
    대조하므로, 어긋나면 재작성이 걸린다 — 부탁이 판정으로 바뀐다.

    말 밀도를 함께 박는 이유(실측): 일반 기준 4.5자/초면 30초에 135자인데 채이홈 히트작은
    264~377자였다. 규칙 위반이 아니라 아무 경고 없이 **히트작의 1/3로 헐거운** 대본이
    나오고 있었다. 칸당 평균 글자수까지 줘야 실제로 채워진다(117자 → 269자, 실측).
    """
    if not style or not style.get("beat_roles"):
        return ""
    roles = style["beat_roles"]
    templates = style.get("templates") or {}
    # 칸 설명은 기존 beat_chain_json(사람이 읽는 자연어)을 순서대로 빌려 쓴다 —
    # 같은 내용을 두 곳에 적지 않기 위해서다(0순위-B). 개수가 안 맞으면 있는 만큼만.
    descs = style.get("beat_descs") or dict(zip(roles, style.get("beat_chain") or []))
    lines = []
    for i, role in enumerate(roles, 1):
        tmpl = templates.get(role) or []
        tail = ("\n     쓸 수 있는 문장틀(빈칸만 우리 소재에 맞게 채워라. 틀 자체를 새로 짓지 마라): "
                + " / ".join('"%s"' % _sanitize(x) for x in tmpl)) if tmpl else ""
        lines.append('  %d) role="%s" — %s%s' % (i, role, _sanitize(descs.get(role, "")), tail))
    chars = style.get("chars_per_30s") or 0
    dens = ""
    if chars:
        target = int(chars * seconds / 30)
        dens = ("\n- 전체 %d초에 **%d자 안팎**으로 꽉 채워라(이 스타일 히트작의 실제 밀도다). "
                "칸 하나에 평균 %d자 — 한 문장으로 끝내지 말고 2~3문장씩 써라. "
                "말이 비면 이 스타일이 아니다." % (seconds, target, max(1, target // len(roles))))
    return ("★[스타일: %s] — 아래 칸을 **이 순서 그대로** 채워라(순서를 바꾸거나 칸을 빼면 반려된다).\n"
            % _sanitize(style.get("name") or "")
            + "\n".join(lines)
            + "\n- 각 칸의 role 값을 위와 **똑같이** 돌려줘라(검사기가 대조한다)." + dens
            + voice_block(style))


def voice_block(style):
    """표현 사전 → 프롬프트 블록(2026-08-17). 없으면 ''(기존 경로 그대로 = 회귀 0).

    ## 왜 이게 따로 있나 — 사실과 표현을 가른다 (사장님 모델)

        사실 = "녹는다"             ← 재료(대본·리뷰·상세페이지)에서 온다
        표현 = "사르르 / 퐁신퐁신"   ← 채널 말버릇. 스타일이 갖는다. 어느 제품에나 쓴다
        결과 = "사르르 녹는데 퐁신퐁신해서"

    합쳐진 완제품("입에서 사르르 녹는")을 **재료**로 주면 원본을 그대로 베끼게 된다.
    갈라 놓으면 원본에 없던 표현을 **새로 만들어** 쓴다.

    3안 실측(2026-08-16, 계란+요거트 빵 3편·가족갈등 반전형):
      A 대본 통째 → 말버릇 4개(전부 원본에서 베낌)·383자
      B 사실만    → 말버릇 1개·게이트 **실패**(고조)·254자
      C 사실+사전 → 말버릇 **8개**·통과·**323자** ← 원본에 없던 "퐁신퐁신·쫙"을 새로 만들었다
    ★밀도 문제도 같이 풀렸다 — 억지로 늘린 게 아니라 말맛이 살면서 자연히 붙는다.
    """
    v = (style or {}).get("voice") or {}
    if not v:
        return ""
    rows = []
    for key, label in (("onomatopoeia", "의성·의태어"), ("intensifier", "강조어"),
                       ("exclaim", "감탄"), ("endings", "종결 말버릇")):
        vals = [x for x in (v.get(key) or []) if str(x).strip()]
        if vals:
            rows.append("  · %s: %s" % (label, " / ".join(_sanitize(str(x)) for x in vals)))
    tone = _sanitize(str(v.get("tone_note") or "").strip())
    if not rows and not tone:
        return ""
    out = "\n★[이 스타일의 말버릇] — 아래 표현을 **사실에 얹어** 써라."
    if tone:
        out += "\n  · 말투: " + tone
    if rows:
        out += "\n" + "\n".join(rows)
    # ★재료(사실)와 섞이지 않게 못을 박는다 — 이 구분이 무너지면 원본 베끼기로 되돌아간다.
    out += ("\n  ※ 사실(무엇이 좋은가)은 재료에서 가져오고, 위 표현은 **말맛**으로만 얹어라. "
            "재료 문장을 그대로 옮기지 말고, 사실 + 위 표현으로 **새 문장을 지어라**.")
    return out


def assemble_bank_context(store, category, k=5):
    """스파인 charter + 부품 top-k + ★우승 대본 few-shot 합본. 없으면 ''(호출부는 빈 문자열이면
    기존 헌장만 써서 회귀0)."""
    # ★category 비어도(자동유형 경로는 video_type=None→"") 스파인을 건너뛰지 마라(2026-07-23
    # 실측 버그: `if category`가 falsy라 pick을 아예 안 불러 승인 스파인 4개가 죽어 있었다).
    # pick_spine_for_category(None)은 fit_categories 없는 범용 스파인을 perf 최고로 반환한다.
    spine = store.pick_spine_for_category(category or None)
    # 스파인(아크) + 말투(parts_block) + 전개 패턴(content_block) + ★우승대본 few-shot(2026-07-26) 4층 주입.
    blocks = [x for x in (spine_charter(spine), parts_block(store, k), content_block(store),
                          winners_block(store, category)) if x]
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
