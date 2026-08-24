"""생성 프롬프트 주입용 은행 컨텍스트 조립(Phase2 토대). store 읽기만, Gemini 없음.
★중괄호 소독 필수 — script_generate 프롬프트가 .format()을 돌린다(_STORY_RULES_CORE 옆에 낀다)."""
import hashlib
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
            "절대 가져오지 마라**. 오직 우리 영상의 소재로만 써라 — 훅의 '강도와 리듬'만 "
            "흡수하고 소재는 100% 우리 것.\n"
            "  ★우리 영상의 소재는 위 [재료 대본들]의 **[대본 1]**에 나온 제품·소재 하나뿐이다. "
            "이 블록(예시·부품)에 등장하는 어떤 제품도 우리 소재가 될 수 없다.]\n"
            + "\n\n".join(lines))


#: 칸 이름(role)만 있고 설명이 없을 때 쓰는 최소 안내(2026-08-22).
#  ★"설명 없음"을 그대로 내보내면 모델이 칸 이름만 보고 추측한다 — 그게 08-21
#    "문장이 서로 안 이어진다"의 한 축이었다. 뜻이 분명한 역할어는 여기서 메꾼다.
_ROLE_FALLBACK = {
    "hook": "첫 3초 — 가장 강한 한 방으로 연다",
    "bait": "첫 3초 — 가장 강한 한 방으로 연다",
    "title": "화면 제목 — 궁금증을 거는 한 줄",
    "problem": "무엇이 불편했는지 구체적으로",
    "pain": "무엇이 불편했는지 구체적으로",
    "situation": "어떤 상황이었는지 구체적으로",
    "context": "어쩌다 이걸 찾게 됐는지",
    "origin": "원래 이게 왜 문제였는지",
    "mistake": "다들 하는 그 실수",
    "reveal": "반전 — 알고 보니 무엇이었는지",
    "notice": "무엇을 눈치챘는지",
    "source": "누구에게서 알게 됐는지",
    "authority": "누가 만들었나 · 왜 믿을 만한가",
    "proof": "정말 그런지 보여주는 근거",
    "evidence": "정말 그런지 보여주는 근거",
    "mechanism": "왜 그렇게 되는지 — 구조·원리",
    "spec": "핵심 기능·사양을 한 줄로",
    "method": "어떻게 쓰는지 — 동작을 눈에 보이게",
    "steps": "순서대로 — 몇 번 만에 끝나는지",
    "demo": "실제로 해 보이는 장면",
    "ease": "얼마나 간단한지",
    "usage": "어디에 쓰면 좋은지",
    "targets": "어떻게 해결하는지",
    "cases": "이렇게까지 쓰더라 — 활용 사례",
    "twist": "진짜 반전 — 예상 밖의 쓰임",
    "spread": "어쩌다 소문이 퍼졌는지",
    "scale": "얼마나 화제인지",
    "texture": "먹었을 때·썼을 때의 감각",
    "result": "쓰고 나서 어떻게 달라졌는지",
    "price": "가격 — 얼마나 부담 없는지",
    "benefit": "그래서 무엇이 좋아지는지",
    "witness": "주변 반응 — 누가 뭐라고 했는지",
    "escalation": "한 단계 더 — 고조 연결어로 시작한다",
    "bonus": "덤으로 좋은 점 하나 더",
    "regret": "진작 알았으면 — 뒤늦은 아쉬움",
    "fit": "어떤 사람에게 맞는지",
    "emotion": "그때 기분을 한 줄로",
    "conflict": "무엇이 부딪혔는지",
    "intro": "무엇을 몇 개 소개하는지 한 줄로",
    "item": "항목 하나 — 무엇이고 왜 좋은지",
    "adverb": "한 단계 더 — 고조 연결어로 시작한다",
    "cta": "댓글 유도 — 받을 것을 반드시 말한다",
}

#: 설명이 CTA 문구인지(마지막 칸 것인지) 알아보는 표식.
_CTA_MARK = ("남겨주", "댓글에")


def beat_descs(style):
    """칸(role) → 설명. **모든 칸이 설명을 갖는다**(2026-08-22).

    ## 왜 zip()을 쓰면 안 되나 (라이브 실측)

    예전엔 `dict(zip(roles, beat_chain))`이었다. `zip`은 **짧은 쪽에서 조용히 끊긴다** —
    오류도 경고도 없이 뒤쪽 칸이 설명 없이 나간다. 서버 43개 스파인 실측(08-22):

      · 어긋난 스파인 **10개**
      · id=52 가족갈등 반전형: 칸 10 · 설명 5 → 뒤 5칸(method·result·escalation·regret·cta) 무설명
      · **6개는 설명이 0개** → 8칸 전부가 role 이름만 나간다(다이소 내부인형 등)

    설명이 없으면 모델은 칸 이름만 보고 추측한다. 실제 피해(08-21 단정 명령형 스콘):
    cta 칸에 설명이 없어 "다들 이 방법으로 편하게 만드시길 바라요"로 끝나고 **CTA가 증발**했다.

    ## CTA는 마지막 칸에 앵커한다

    beat_chain의 마지막 원소는 대개 CTA 문구인데, 칸이 더 많으면 그게 **중간 칸으로 밀린다**.
    실측(08-21 13:11 가족갈등 반전형): 5번 칸 `reveal`이 "댓글에 '불꽃' 남겨주시면 좌표
    드릴게요"를 말하고 cta 칸에서 또 말했다 — 대본 한가운데서 댓글을 유도한 것이다.
    → CTA 문구로 보이는 설명은 **마지막 칸에 붙이고**, 나머지를 앞에서부터 순서대로 채운다.

    ★`beat_descs`가 스타일에 직접 들어 있으면 그것을 그대로 쓴다(옛 경로 = 회귀 0).
    """
    roles = list((style or {}).get("beat_roles") or [])
    if not roles:
        return {}
    given = (style or {}).get("beat_descs")
    if given:
        out = dict(given)
    else:
        chain = [str(x).strip() for x in ((style or {}).get("beat_chain") or []) if str(x).strip()]
        out = {}
        # ★CTA 문구는 마지막 칸 몫으로 떼어둔다 — 중간 칸으로 밀리지 않게.
        tail_desc = ""
        if chain and len(chain) < len(roles) and any(m in chain[-1] for m in _CTA_MARK):
            tail_desc = chain.pop()
        for role, desc in zip(roles, chain):        # 남은 것을 앞에서부터
            out[role] = desc
        if tail_desc:
            out[roles[-1]] = tail_desc
    # 빈 칸은 역할어 기본 안내로 메운다. 그것도 없으면 최소한 이름이라도 문장으로.
    for role in roles:
        if not str(out.get(role) or "").strip():
            out[role] = _ROLE_FALLBACK.get(role, "%s — 이 칸의 역할에 맞게 쓴다" % role)
    return out


def _rotate(items, seed, role):
    """이 job·이 칸에서 몇 번째 틀부터 보여줄까 — 목록을 회전해 돌려준다(2026-08-23).

    ★why: `style_block`은 문장틀을 **항상 같은 순서**로 실었고, 모델은 특정 문장에
      쏠린다. 다이소 훅 10개로 8회 뽑은 실측 — 10개 중 **6개가 한 번도 안 나왔다**
      (6번 3회·7번 3회에 몰림). 틀을 늘려도 순서가 고정이면 소용이 없다.
    ★랜덤이 아니라 seed(job_id) 해시다 — 같은 job을 다시 돌리면 같은 대본이 나온다.
      role을 섞어 한 대본 안에서도 칸마다 다른 번호에서 시작한다.
      (조립 경로의 `spine_fill._rotate_idx`와 같은 규칙 — 그쪽은 하나를 고르고
       여기는 순서를 돌린다는 점만 다르다.)
    ★seed가 없으면 원본 그대로 = 회귀 0.
    """
    n = len(items or [])
    if not seed or n <= 1:
        return list(items or [])
    h = hashlib.md5(("%s|%s" % (seed, role)).encode("utf-8")).hexdigest()
    k = int(h[:8], 16) % n
    return list(items[k:]) + list(items[:k])


def style_block(style, seconds=30, seed=""):
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
    # 칸 설명은 beat_descs()가 한 곳에서 정한다(0순위-B) — 짝짓기 규칙이 두 군데에
    # 적혀 있으면 반드시 어긋난다. zip()으로 조용히 끊기던 것을 그 함수가 막는다.
    descs = beat_descs(style)
    lines = []
    for i, role in enumerate(roles, 1):
        # ★job마다 다른 틀에서 시작한다 — 순서가 고정이면 모델이 앞쪽에 쏠린다.
        tmpl = _rotate(templates.get(role) or [], seed, role)
        tail = ("\n     쓸 수 있는 문장틀(빈칸만 우리 소재에 맞게 채워라. 틀 자체를 새로 짓지 마라): "
                + " / ".join('"%s"' % _sanitize(x) for x in tmpl)) if tmpl else ""
        lines.append('  %d) role="%s" — %s%s' % (i, role, _sanitize(descs.get(role, "")), tail))
    chars = style.get("chars_per_30s") or 0
    dens = ""
    if chars:
        # 목표 글자수는 script_gate가 한 곳에서 정한다(0순위-B) — 프롬프트와 판정이 다른
        # 수를 쓰면 "시킨 대로 썼는데 반려"가 난다. 그 안에 말속도 천장(8.19자/초)이 있다.
        from shopping_shorts.script_gate import density_target
        target = density_target(style, seconds)
        dens = ("\n- 전체 %d초에 **%d자를 넘기지 마라** — 이 길이가 플랫폼 규격이다(히트작 밀도를 말속도로 환산한 값). "
                "칸 하나에 평균 %d자 — 한 문장으로 끝내지 말고 2~3문장씩 써라. "
                "말이 비면 이 스타일이 아니다." % (seconds, target, max(1, target // len(roles))))
    return ("★[스타일: %s] — 아래 칸을 **이 순서 그대로** 채워라(순서를 바꾸거나 칸을 빼면 반려된다).\n"
            % _sanitize(style.get("name") or "")
            + "\n".join(lines)
            + "\n- 각 칸의 role 값을 위와 **똑같이** 돌려줘라(검사기가 대조한다)." + dens
            # ★장르 규칙(반말체·CTA금지)을 프롬프트에도 싣는다 — 게이트만 검사하면
            #   모델은 그 판정을 못 보고 계속 같은 걸 쓴다(2026-08-22 사장님 화면).
            + genre_block(style)
            + voice_block(style))


def genre_block(style):
    """유튜브 썰 장르 규칙 → 프롬프트 블록(2026-08-22). 선언 안 한 스타일은 ''(회귀 0).

    ## 왜 필요한가 — 판정만 있고 지시가 없었다

    `script_gate`는 유튜브 썰(hook_3s)에 **반말체**를 검사하고 `no_cta`면 CTA를 반려한다.
    그런데 **프롬프트 어디에도 그 말이 없었다** — 유튜브 스파인 3개(55·56·60)는 `voice`
    사전이 비어 `voice_block`이 빈 문자열을 돌려준다.
    더 나쁜 건 CTA다: `_STORY_RULES_CORE`가 "댓글에 'OO' 남겨주시면 …드릴게요"를
    **쓰라고 시키는데** 게이트는 그걸 쓰면 반려한다 — 시켜놓고 벌주는 구조였다.
    실측(2026-08-22 사장님 화면): A안·B안 둘 다 `말끝(반말체)`·`CTA 금지` 경고를 단 채 나왔다.

    ★모델은 판정을 못 본다. 고치려면 프롬프트에서 못 박아야 한다.
      (판정만 두면 아무도 안 고치고, 프롬프트만 두면 안 지킨다 — 둘 다 필요하다)
    """
    out = []
    if (style or {}).get("hook_3s"):
        out.append(
            "\n★[말투 — 이 장르의 서명] 처음부터 끝까지 **반말체**로 써라. "
            "존댓말을 단 한 문장도 쓰지 마라.\n"
            "  · 쓸 것:  ~했음 / ~하더라 / ~라는 거 / ~인데 / ~더라고 / ~임\n"
            "  · 쓰지 말 것: ~거든요 / ~드릴게요 / ~예요 / ~습니다 / ~하세요\n"
            "  · 첫 문장(훅)의 말투를 **끝까지 그대로** 유지해라 — 중간에 존댓말로 "
            "돌아가면 다른 사람이 말하는 것처럼 들린다.")
    if (style or {}).get("no_cta"):
        out.append(
            "\n★[CTA 금지] 댓글·구독·좋아요·링크를 **부르지 마라**. "
            "'댓글에 OO 남겨주세요' 류를 쓰면 반려된다.\n"
            "  · 이 장르는 완시청으로 먹는다 — 행동을 요구하면 흐름이 끊긴다"
            "(실측: 이 계열 히트작 전부 CTA가 없다).\n"
            "  · 마지막 칸도 CTA가 아니라 **이야기의 마무리**로 닫아라.")
    if (style or {}).get("hook_conceal"):
        out.append(
            "\n★[훅에서 정체 숨기기] 첫 문장(훅)에 **제품 이름을 쓰지 마라**. "
            "'이거 / 이것 / 이 제품'처럼 가려서 말해라.\n"
            "  · O: \"여러분 다이소 가면 이거 꼭 사오세요\"\n"
            "  · X: \"여러분 다이소 가면 이 앞머리 고데기 꼭 사오세요\" "
            "(정체가 나오면 궁금할 이유가 없어져 훅이 죽는다)\n"
            "  · 무엇인지는 뒤쪽 칸에서 밝혀라 — 그때까지 끌고 가는 게 이 구조의 힘이다.")
    return "".join(out)


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


#: 은행(학습 재료)이 재료 대본보다 몇 배까지 길어도 되는가.
#  ★2026-08-18 사고의 물리적 원인이 이 비율이다 — 실측: 재료 750자(네일 3편) vs
#  은행 2,822자(3.8배). 그 상태에선 은행 안의 구체적 소재 하나만 있어도 대본이
#  그쪽으로 끌려간다(A안이 통째로 '주방 기름 가림막'). 부품이 더러워서가 아니라
#  **학습 재료가 재료를 압도해서** 터진 것이다.
#  1.5배로 잡은 근거: 은행은 '말투·구조'만 담당하므로 재료보다 길 이유가 없다.
#  여유를 조금 두는 것은 스파인 헌장(뼈대)이 고정비로 들어가기 때문이다.
_BANK_BUDGET_RATIO = 1.5


def assemble_bank_context(store, category, k=5, source_chars=0):
    """스파인 charter + 부품 top-k + ★우승 대본 few-shot 합본. 없으면 ''(호출부는 빈 문자열이면
    기존 헌장만 써서 회귀0)."""
    # ★category 비어도(자동유형 경로는 video_type=None→"") 스파인을 건너뛰지 마라(2026-07-23
    # 실측 버그: `if category`가 falsy라 pick을 아예 안 불러 승인 스파인 4개가 죽어 있었다).
    # pick_spine_for_category(None)은 fit_categories 없는 범용 스파인을 perf 최고로 반환한다.
    spine = store.pick_spine_for_category(category or None)
    # 스파인(아크) + 말투(parts_block) + 전개 패턴(content_block) + ★우승대본 few-shot(2026-07-26) 4층 주입.
    blocks = [x for x in (spine_charter(spine), parts_block(store, k), content_block(store),
                          winners_block(store, category)) if x]
    if not blocks:
        return ""
    # ★예산 초과분은 **뒤에서부터 블록 단위로** 뺀다(2026-08-18).
    #   순서가 곧 중요도다: 스파인 헌장(뼈대) > 말버릇 > 전개 패턴 > 우승 예시 전문.
    #   뒤로 갈수록 '실제 문장'이라 소재를 흘릴 위험이 크고, 없어도 뼈대는 살아 있다.
    #   ⚠️글자 단위로 자르지 않는다 — 문장 중간이 잘리면 지시가 반쪽이 돼 더 나쁘다.
    #   ⚠️첫 블록(스파인)은 무슨 일이 있어도 남긴다. 그게 없으면 스타일 자체가 사라진다.
    #   source_chars=0(안 넘긴 옛 호출)이면 종전 그대로 = 회귀 0.
    if source_chars and source_chars > 0:
        budget = int(source_chars * _BANK_BUDGET_RATIO)
        while len(blocks) > 1 and sum(len(b) for b in blocks) > budget:
            blocks.pop()
    # ★소재 오염 차단(2026-08-18 사장님 제보 "대본을 뽑으니 이상한 게 나온다").
    #   실측: 담긴 재료 3편이 전부 다이소 네일펜인데 A안이 통째로 '주방 기름 가림막'으로
    #   나왔다(work 3b8e5099a22e). 이 블록은 2,822자짜리 학습 재료라 재료 대본보다 길고
    #   구체적인데, 부품 문장들이 소재 중립이 아니다 — 어제 저녁(08-17 21:47 KST) 승인분에
    #   '주방 기구·주방 동선·요리 결과'처럼 소재가 박힌 것이 대량으로 들어왔다.
    #   각 하위 블록이 저마다 "소재는 가져오지 마라"를 말해도, 블록이 4겹이면 그 경고가
    #   중간에 묻힌다. **맨 끝에서 한 번 더 못 박는다** — 마지막 지시가 가장 강하게 남는다.
    blocks.append(
        "★★이 블록 전체(아크·부품·전개·우승예시)는 **말투·구조·리듬 참고용**이다. "
        "여기 등장하는 제품·소재·장소(주방·요리 등)는 우리 영상의 소재가 아니다. "
        "우리 소재는 오직 [재료 대본들]의 [대본 1]에 나온 것 하나뿐이며, "
        "그와 다른 물건 이야기가 한 줄이라도 들어가면 반려된다.")
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
