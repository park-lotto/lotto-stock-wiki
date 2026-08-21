# -*- coding: utf-8 -*-
"""구조 템플릿에 **슬롯 값만 끼워** 대본을 조립한다(2026-08-19).

사장님 지시:
> "구조템플릿 만드는게 중요해. 같은 해외영상이나 여러영상을 가져와도
>  거기에 딱 들어갈 말들만 있음 되게"

## 왜 만들었나 — 실측으로 드러난 문제

같은 날 실제 생성(spine 56 · 재료 마늘다지기)을 돌려보니 재료는 제대로 실렸는데
**틀이 안 지켜졌다**:

    템플릿   "이게 원래는 {본래용도} 개발된 제품이었음"
    실제     "이게 원래는 절구 소음 없이 마늘을 다지라고 개발된 주방 도구였거든요?"
                                                              ↑ 어미를 새로 씀 → 게이트 FAIL
    그리고   twist 칸이 twist+고조+CTA를 다 삼켰고, no_cta 스타일인데 **CTA가 붙었다**.

원인은 하나다 — 지금 구조는 템플릿을 **프롬프트에 참고로 넣고 모델이 문장을 쓴다.**
참고는 지켜질 때도 있고 아닐 때도 있다. 매번 흔들리는 걸 프롬프트로 못 고친다
(memory: 프롬프트가 말해도 아무도 검사 안 하면 안 지켜진다).

## 그래서 뒤집는다

    모델이 하는 일 = **슬롯 값을 뽑는 것**(sul_facts·product_facts가 이미 한다)
    문장을 만드는 일 = **이 모듈**(템플릿 문자열 + 슬롯. 모델 호출 0)

이러면 어떤 영상을 가져와도 결과 문장은 **항상 같은 틀**이고, 갈리는 건 슬롯뿐이다.
CTA가 붙을 자리가 없고, 어미가 흔들릴 자리도 없다.

## 슬롯 8종 — 어디서 오나 (표는 sul_facts.SLOT_SOURCE가 정본)

    {제품} {효능} {효능2} {나라}   ← product_facts   (쿠팡 상세·리뷰)
    {본래용도} {속성} {용도} {제품군} ← sul_facts     (영상 자막)

`{용도들}`만 파생 슬롯이다 — misuses 여러 개를 사례 나열 문장으로 잇는다.
"""
import re

# 템플릿에 쓰이는 슬롯 이름. 여기 없는 이름이 템플릿에 있으면 그 템플릿은 못 쓴다
# (모르는 슬롯을 빈칸으로 남기면 "이게 원래는  개발된 제품이었음"이 나간다).
_YT_SLOT_NAMES = ("제품", "효능", "효능2", "효능3", "나라", "본래용도", "속성",
                  "용도", "용도2", "용도3", "용도끝", "용도들", "제품군",
                  # 발명품형(2026-08-20). 이 갈래 23편의 힘이 전부 여기서 나온다.
                  "계기")

# ★인스타 슬롯(2026-08-19). 재료 출처가 다르다 — 유튜브는 쿠팡+유튜브 자막이지만
#   인스타는 **릴 전사만** 본다(다이소·중국 제품은 쿠팡 1:1 매칭이 안 된다는 사장님 지시).
#   표의 정본은 `insta_facts.SLOT_SOURCE`. 파생 슬롯(대상2·대상들)만 여기서 만든다.
#   ⚠️ 엔진(fix_josa·pick_template·fill)은 **두 플랫폼이 공용**이다. 조사 교정 같은
#      한국어 문법 처리를 플랫폼별로 두 벌 만들면 같은 사고를 두 번 겪는다(0순위-B).
_INSTA_SLOT_NAMES = ("사용법", "적용대상", "적용대상2", "적용대상들",
                     "효과", "수치", "차별점", "불편함", "가격")

SLOT_NAMES = _YT_SLOT_NAMES + _INSTA_SLOT_NAMES

_SLOT_RE = re.compile(r"\{([^{}]+)\}")


def slots_in(template):
    """이 템플릿이 요구하는 슬롯 이름들."""
    return [m.group(1) for m in _SLOT_RE.finditer(template or "")]


def _first(v):
    """리스트면 첫 항목, 문자열이면 그대로. 없으면 ''."""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return str(v or "").strip()


# ── 조사 자동 교정 ────────────────────────────────────────────────────────
# 템플릿은 "{속성}을 눈치채고"·"{용도}로 쓰는가"처럼 슬롯 **바로 뒤에 조사**가 붙는다.
# 슬롯 값은 영상마다 달라 받침이 갈리므로, 한 형태로 고정해두면 반드시 어색해진다
# (실측: "바지 밑단 줄임로", "봉 없이 걸린다을").
# ★교정은 치환하는 그 자리에서 한 번만 한다 — 나중에 문장 전체를 훑어 고치면
#   슬롯이 아닌 원래 문장의 조사까지 건드린다.
# ★순서가 중요하다 — 앞에서부터 startswith로 맞춰보므로 **긴 것이 먼저** 와야 한다.
#   실측 사고(2026-08-19): ("이","가")가 앞에 있어서 "{제품군}이었음"의 '이'를 주격조사로
#   보고 받침 없는 값에 '가'를 넣었다 → **"주얼리가었음"**. 서술격조사 '이다'의 활용이라
#   규칙은 따로 있다: 받침 O "주방도구이었음" / 받침 X "주얼리였음".
_JOSA_PAIRS = (("이었", "였"), ("이라고", "라고"), ("이야", "야"), ("으로", "로"),
               ("을", "를"), ("은", "는"), ("이", "가"), ("과", "와"))


def _batchim(word):
    """마지막 글자의 종성 코드. 한글이 아니면 None(=건드리지 않는다)."""
    w = (word or "").strip()
    if not w:
        return None
    ch = w[-1]
    if not ("가" <= ch <= "힣"):
        return None
    return (ord(ch) - 0xAC00) % 28


def fix_josa(value, tail):
    """`value` 뒤에 오는 `tail`의 첫 조사를 value의 받침에 맞게 고친 (조사, 남은꼬리).

    '로/으로'만 규칙이 다르다 — ㄹ 받침은 받침이 있어도 '로'를 쓴다("줄로", "칼로").
    한글이 아니면(영문·숫자) 판단하지 않고 원문 그대로 둔다.
    """
    b = _batchim(value)
    for withb, nob in _JOSA_PAIRS:
        for form in (withb, nob):
            if tail.startswith(form):
                rest = tail[len(form):]
                if b is None:
                    return form, rest
                if withb == "으로":
                    want = "로" if b in (0, 8) else "으로"   # 0=받침없음, 8=ㄹ
                elif withb == "이었":
                    # 서술격조사 — 받침 없으면 '였'으로 줄어든다("주얼리였음").
                    want = "이었" if b else "였"
                else:
                    want = withb if b else nob
                return want, rest
    return "", tail


def _nth(v, i):
    """리스트의 i번째. 없으면 ''(그 슬롯을 쓰는 템플릿은 자동으로 안 걸린다)."""
    if isinstance(v, (list, tuple)):
        return str(v[i]).strip() if len(v) > i else ""
    return str(v or "").strip() if i == 0 else ""


def _last(v):
    """리스트면 마지막 항목. 하나뿐이면 그것(겹침을 피할 방법이 없다)."""
    if isinstance(v, (list, tuple)):
        v = v[-1] if v else ""
    return str(v or "").strip()


def _cases_and_last(items):
    """엉뚱한 사용처 목록 → (나열에 쓸 것들, 반전에 쓸 마지막 하나).

    ★왜 나누나(2026-08-20 실측으로 잡은 재발 버그): `용도끝`을 그냥 **마지막 항목**으로
      뽑고 있었는데, `cases`도 앞에서 3개까지 쓴다. 사용처가 2~3개면 cases가 이미 말한
      것을 twist가 그대로 반복해 **반전이 죽는다**.

        misuses 3개 → cases "…고수들은 슬라이딩 신발장까지 심지어 **2층 수납함**까지"
                      twist "근데 미친 사용법은 따로 있었는데 **2층 수납함**"   ← 같은 말

      "twist는 cases에서 이미 말한 것을 또 말하면 안 된다"는 규칙은 원래 주석에 적혀
      있었지만, 뽑는 방식이 그걸 못 지켰다(적어두는 것만으로는 안 지켜진다).
      히트작 200편 중 오용형 정밀분해 20편의 사용처 개수 분포가 2개 5편·3개 6편이라
      **절반 이상(55%)이 이 구간**이었다.

    ★실측 순서와도 맞는다: 20편의 등장 순서가 거의 `나열 → 고조 → 클라이맥스`이고,
      클라이맥스가 마지막인 편이 14/20이다. 마지막 하나를 반전에 남겨두는 게 원본의 결이다.

    사용처가 1개뿐이면 반전을 만들 재료가 없다 → 반전 몫을 비운다. 그러면 twist 템플릿이
    안 걸려 `missing`으로 넘어가고, 호출부가 모델에 맡긴다(겹친 문장을 내놓는 것보다 낫다).
    """
    xs = items
    if isinstance(xs, str):
        xs = [xs]
    xs = [str(x).strip() for x in (xs or []) if str(x).strip()]
    if len(xs) < 2:
        return xs, ""
    return xs[:-1], xs[-1]


def _join_cases(items, max_n=3):
    """엉뚱한 사용처 여러 개 → 사례 나열 한 문장.

    실측 오용형 대본의 결을 그대로 쓴다("…로 쓰는가 하면 …로도 쓰고").
    1개뿐이면 나열이 아니라 단문이 정직하다.
    """
    xs = [str(x).strip() for x in (items or []) if str(x).strip()][:max_n]
    if not xs:
        return ""
    if len(xs) == 1:
        _j, _ = fix_josa(xs[0], "로")
        return "%s%s 쓰더라고요" % (xs[0], _j or "로")
    _j, _ = fix_josa(xs[0], "로")
    head = "%s%s 쓰는가 하면" % (xs[0], _j or "로")
    rest = ", ".join(xs[1:])
    # ★마지막 항목에도 조사를 맞춘다(실측: "아이들 간식용로도" — 나열 꼬리를 빼먹었다).
    _j2, _ = fix_josa(xs[-1], "로")
    return "%s %s%s도 쓰고요" % (head, rest, _j2 or "로")


def merge_sul(facts_list):
    """여러 영상에서 뽑은 썰 재료를 **한 벌로 합친다**(2026-08-19 사장님 지시).

    > "같은 해외영상이나 여러영상을 가져와도 거기에 딱 들어갈 말들만 있음 되게"

    ★왜 필요한가(실측): 한 편만 보면 칸이 빈다. 라이브 재료 2편을 각각 돌렸더니
      둘 다 `misuses`(엉뚱한 사용처)가 **0건**이라 오용형 5칸 중 `cases`·`twist`가
      통째로 못 채워졌다. 소개 영상 한 편에는 '원래 용도'는 있어도 '엉뚱한 용도'가
      없는 게 정상이다 — 그건 여러 편을 겹쳐야 보인다.

    합치는 규칙은 단순하다: 리스트는 **순서를 지키며 이어붙이고 중복만 뺀다**.
    (점수를 매겨 고르지 않는다 — 무엇이 좋은 사례인지는 재료가 아니라 편집이 정한다)

    ⚠️ **같은 소재의 영상만 합쳐라.** 서로 다른 제품 6편을 합쳐봤더니(실측 2026-08-19)
      "원래는 수납으로 개발됐는데 / 사진의 입체화를 눈치채고 / 아이들 간식으로 쓴다"는
      **말이 안 되는 대본**이 나왔다. 슬롯은 다 찼지만 소재가 섞인 것이다.
      실무 호출부는 job에 **담긴 영상들**(같은 주제로 사장님이 담은 것)을 넘기므로
      이 조건이 자연히 지켜진다 — 아무 영상이나 넘기는 호출부를 만들지 마라.
    """
    out = {}
    for f in (facts_list or []):
        if not isinstance(f, dict):
            continue
        for k, v in f.items():
            if isinstance(v, bool):
                # ★불리언은 이어붙이는 값이 아니다 — **하나라도 false면 false**로 본다
                #   (오용형이 아닌 영상이 섞였는데 통과시키면 대본이 공허해진다).
                out[k] = bool(out.get(k, True)) and v
                continue
            if isinstance(v, str):
                v = [v] if v.strip() else []
            if not isinstance(v, (list, tuple)):
                continue
            cur = out.setdefault(k, [])
            for x in v:
                x = str(x).strip()
                if x and x not in cur:
                    cur.append(x)
    return out


def slots_from_facts(product_facts=None, sul=None):
    """product_facts + sul_facts → 슬롯 dict. **빈 값은 아예 담지 않는다** —
    담아두면 템플릿이 "채워졌다"고 보고 빈칸이 그대로 나간다."""
    pf = product_facts or {}
    sf = sul or {}
    why = pf.get("why") or []
    if isinstance(why, str):
        why = [why]
    # ★쿠팡 재료가 있으면 그쪽이 먼저다(상세페이지·리뷰가 영상보다 정확하다).
    #   없으면 **영상에서 뽑은 값**으로 채운다 — 해외 원본만 담는 경우엔 쿠팡 상품이
    #   아예 없어서, 이 폴백이 없으면 은폐형은 조립 자체가 불가능하다(2026-08-19).
    ben = sf.get("benefits") or []
    if isinstance(ben, str):
        ben = [ben]
    _cases, _last_use = _cases_and_last(sf.get("misuses"))
    out = {
        "제품": _first(pf.get("title")) or _first(sf.get("product_name")),
        "효능": (_first(why[0]) if len(why) > 0 else "") or _nth(ben, 0),
        "효능2": (_first(why[1]) if len(why) > 1 else "") or _nth(ben, 1),
        # 고조('심지어 …까지')를 받는 세 번째 장점. 은폐형 twist가 쓴다 —
        # 게이트가 고조 1회를 요구하는데 은폐형 템플릿엔 그 자리가 없었다(실측).
        "효능3": (_first(why[2]) if len(why) > 2 else "") or _nth(ben, 2),
        "나라": _first(pf.get("origin")) or _first(sf.get("origin_country")),
        "본래용도": _first(sf.get("original_use")),
        "속성": _first(sf.get("hidden_property")),
        # ★cases와 twist는 **겹치면 안 된다**. 그래서 반전 몫을 먼저 떼어낸 뒤
        #   나머지만 나열에 준다(`_cases_and_last`). 아래 슬롯은 전부 그 결과를 쓴다.
        "용도": _nth(_cases, 0),
        # ★실측 대본의 cases는 명사 나열이 아니라 **초보 vs 고수 대비**다
        #   ("초보 주부들은 기껏해야 환기 정도가 전부였음 / 하지만 고수 주부들은
        #     주방 벽에 설치해서 시원하게 요리한다고"). 그래서 두 번째 사례가 필요하다.
        "용도2": _nth(_cases, 1),
        # 고조 연결어('심지어')를 받는 세 번째 사례. 실측 대본에 그대로 있다
        #   ("…걸어버리면서 심지어 물티슈까지 걸어두고"). 게이트도 고조 1회를 요구한다.
        "용도3": _nth(_cases, 2),
        "용도끝": _last_use,
        "용도들": _join_cases(_cases),
        "제품군": _first(sf.get("category_word")),
        # ★없으면 담기지 않는다(out 마지막에서 빈 값을 턴다) → 계기를 요구하는 템플릿이
        #   자동으로 안 걸리고, 계기 없는 변형이 대신 걸린다. 미담을 지어내지 않는다.
        "계기": _first(sf.get("origin_story")),
    }
    return {k: v for k, v in out.items() if v}


def bigrams(s):
    """한글·숫자만 남긴 **2글자 조각 집합**. 두 문구가 같은 걸 가리키나 볼 때 쓴다.

    형태소 분석 없이 되는 가장 단순한 방법이고, 조사·띄어쓰기 차이를 흡수한다
    ("욕실 수전 물때" ↔ "욕실 수전을 닦는" → '욕실'·'수전'에서 겹친다).

    ★여기 한 벌만 둔다 — `_join_targets`(나열 중복 판정)와
      `insta_facts.gate_by_scene`(장면 근거 판정)이 **같은 판정을 쓴다**.
      두 벌로 두면 한쪽만 고쳐져 어긋난다(0순위-B).

    ★조각은 **낱말 안에서만** 자른다. 통째로 이어붙여 자르면 낱말 경계를 걸친
      쓰레기 조각이 생겨 엉뚱한 게 겹친다(2026-08-19 실측: "보여주는 모습"이
      "…보여주는 장면"과 `는모`·`여주`로 겹쳐 장면 근거 게이트를 그냥 통과했다).
    """
    out = set()
    for w in re.sub(r"[^가-힣0-9]", " ", str(s or "")).split():
        out |= {w[i:i + 2] for i in range(len(w) - 1)}
        if len(w) == 1:
            out.add(w)          # 한 글자 낱말도 근거는 근거다("컵"·"솔")
    return out


def _join_targets(items, max_n=3):
    """적용 대상 여러 개 → "A부터 B까지" 한 덩어리.

    실측 다이소 대본의 결을 그대로 쓴다 — "양말 누런 때부터 신발 찌든 때까지".
    한 제품이 여러 곳에 번지는 게 이 축의 강점이라, 나열이 곧 설득이다.
    1개뿐이면 나열이 아니라 그 하나가 정직하다.
    """
    xs = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    head = xs[0]
    # ★끝은 머리와 **겹치지 않는 것**을 고른다(2026-08-19 실측).
    #   그냥 마지막을 쓰면 "욕실 수전 물때부터 찌든 물때까지"가 나왔다 — 둘 다 물때라
    #   나열의 맛이 없다. 실측 히트작은 다른 것끼리 묶는다("양말 누런 때부터 신발 찌든 때까지").
    #   판정은 2글자 조각이 겹치는지로 본다(`bigrams` — 장면 근거 게이트와 공용).
    hg = bigrams(head)
    tail = next((x for x in reversed(xs[1:max_n]) if not (bigrams(x) & hg)), "")
    if not tail:
        tail = next((x for x in reversed(xs[1:]) if not (bigrams(x) & hg)), xs[-1])
    return "%s부터 %s까지" % (head, tail)


def slots_from_insta(facts):
    """insta_facts 재료 → 슬롯 dict. **빈 값은 아예 담지 않는다**.

    담아두면 pick_template이 "채워졌다"고 보고 빈칸이 그대로 대본에 나간다
    (slots_from_facts와 같은 규약 — 이 원칙을 두 함수가 공유한다).
    """
    f = facts or {}
    out = {
        "사용법":     _first(f.get("how_to")),
        "적용대상":   _first(f.get("targets")),
        # 두 번째 대상 — "심지어 {적용대상2}까지" 같은 고조 문장에 쓴다.
        "적용대상2":  _nth(f.get("targets"), 1),
        "적용대상들": _join_targets(f.get("targets")),
        "효과":       _first(f.get("effects")),
        "수치":       _first(f.get("numbers")),
        "차별점":     _first(f.get("edge")),
        "불편함":     _first(f.get("pain")),
        "가격":       _first(f.get("price")),
    }
    return {k: v for k, v in out.items() if v}


def pick_template(templates, slots):
    """이 역할의 후보 문장들 중 **슬롯이 전부 채워지는 첫 번째**를 고른다.

    ★고르는 규칙이 곧 품질이다: 슬롯이 하나라도 비면 그 문장은 쓰지 않는다.
      대신 슬롯이 더 적은 변형이 있으면 그게 걸린다(그래서 변형을 여러 개 둔다).
      실측 예: bait 변형 3개 중 하나는 {제품군}을 요구하고 둘은 슬롯이 없다 —
      제품군을 못 뽑은 영상에서도 미끼 문장은 나온다.
    """
    ts = usable_templates(templates, slots)
    return ts[0] if ts else ""


def fill_one(template, slots):
    """템플릿 한 줄에 슬롯을 끼운다(조사까지 맞춰서).

    `.format()`을 쓰지 않는다 — 설명용 중괄호가 섞이면 KeyError로 조용히 죽는다
    (2026-08-19 sul_facts 실사고).
    """
    src = template or ""
    out, i = [], 0
    for m in _SLOT_RE.finditer(src):
        out.append(src[i:m.start()])
        val = str(slots.get(m.group(1), "")).strip()
        out.append(val)
        i = m.end()
        josa, rest = fix_josa(val, src[i:])
        if josa:
            out.append(josa)
            i = len(src) - len(rest)
    out.append(src[i:])
    return "".join(out).strip()


def usable_templates(templates, slots):
    """이 재료로 **쓸 수 있는** 문장 후보 전부 — pick_template과 같은 자격 규칙.

    ★pick_template은 '첫 번째'만 돌려주지만 길이를 맞추려면 **후보 전체**가 필요하다.
      자격 규칙을 여기 다시 적지 않고 같은 조건을 한 번만 쓴다(0순위-B).
    """
    out = []
    for t in (templates or []):
        need = slots_in(t)
        if any(n not in SLOT_NAMES for n in need):
            continue                       # 모르는 슬롯이 있는 템플릿은 건너뛴다
        if all(slots.get(n) for n in need):
            out.append(t)
    return out


def target_range(spine, seconds):
    """이 스파인·이 길이의 목표 글자수 (lo, hi) — **script_gate에서 빌려 온다**.

    ★값을 여기 다시 계산하지 않는다. 판정(script_gate.check)과 조립이 서로 다른 수를
      쓰면 "시킨 대로 만들었는데 반려"가 난다(0순위-B). density_target 주석이 같은 말을 한다.
    """
    from shopping_shorts import script_gate as _sg
    tgt = _sg.density_target(spine, seconds)
    cap = int(_sg._speech_cps() * max(5, min(int(seconds or 30), 90)))
    return int(tgt * _sg.DENSITY_LO), min(int(tgt * _sg.DENSITY_HI), cap)


def _measured(beats):
    """게이트가 세는 방식과 **같게** 센다(script_gate.norm — 공백·문장부호 제외)."""
    from shopping_shorts import script_gate as _sg
    return len(_sg.norm(" ".join(b["text"] for b in beats)))


def _has_escalator(text):
    """이 문장에 고조 연결어('심지어' 등)가 들어 있나 — script_gate에서 빌려 온다.

    ★길이를 맞추려고 변형을 바꿀 때 **고조 문장을 갈아치우면 안 된다**(2026-08-21 실사고).
      script_gate는 고조어가 **정확히 1회**일 것을 요구하는데, 다이소형은 그 1회가
      price 칸에만 있다("심지어 {가격}밖에 안 해서"). 30초로 늘리려던 엔진이 그 칸을
      더 긴 다른 변형으로 바꿔 고조가 0회가 됐고 게이트가 반려했다 —
      **길이를 맞추려다 다른 규칙을 깬 것**이다.
    """
    from shopping_shorts import script_gate as _sg
    return _sg._escalation(text or "") > 0


def fill(spine, slots, seconds=None):
    """스파인 + 슬롯 → (beats, missing)

    beats  = [{"role": ..., "text": ...}]  — 채워진 칸만. **한 칸에 한 문장**이다.
    missing= 슬롯이 모자라 못 채운 역할들(호출부가 모델에 맡기거나 재료를 더 뽑는다).

    ★CTA가 붙을 자리가 없다 — 템플릿에 없으면 나올 수 없다. 그게 이 방식의 요점이다.

    ★seconds를 주면 **목표 길이에 맞춰 변형을 고른다**(2026-08-21).
      종전엔 "슬롯이 차는 첫 문장"만 골라 길이를 아예 안 봤다 — 그래서 틀 하나가
      한 길이에만 맞았다(실측 2026-08-21: 20초 목표면 6축 중 4축이 초과로 반려,
      30초 목표면 재료가 적을 때 6축 전부 미달).
      ⚠️seconds가 없으면 **종전과 완전히 같게** 동작한다(유튜브 경로 회귀 0).
    """
    roles = list((spine or {}).get("beat_roles") or [])
    templates = (spine or {}).get("templates") or {}
    cands, chosen, missing = {}, {}, []
    for role in roles:
        ts = usable_templates(templates.get(role), slots)
        # 채워 넣었을 때 실제로 글자가 남는 후보만(빈 문장은 못 쓴다)
        ts = [t for t in ts if fill_one(t, slots)]
        if not ts:
            missing.append(role)
            continue
        cands[role] = ts
        chosen[role] = ts[0]               # 종전 규칙 = 첫 번째

    def _beats():
        return [{"role": r, "text": fill_one(chosen[r], slots)}
                for r in roles if r in chosen]

    if not seconds or not chosen:
        return _beats(), missing

    lo, hi = target_range(spine, seconds)
    # 목표 안으로 들어올 때까지 **한 칸씩** 바꾼다. 매번 가장 크게 줄이는(늘리는) 쪽을
    # 고르되, 반대쪽 한계를 넘기는 교체는 하지 않는다.
    for _ in range(len(roles) * 3 + 6):    # 상한 — 무한루프 방지
        n = _measured(_beats())
        if lo <= n <= hi:
            break
        best, best_gain = None, 0
        for role, ts in cands.items():
            cur = len(fill_one(chosen[role], slots))
            for t in ts:
                if t == chosen[role]:
                    continue
                new_text = fill_one(t, slots)
                # ★고조어 유무가 바뀌는 교체는 하지 않는다 — 개수가 1회에서 벗어나면
                #   길이는 맞아도 게이트가 반려한다(위 _has_escalator 주석의 실사고).
                if _has_escalator(new_text) != _has_escalator(fill_one(chosen[role], slots)):
                    continue
                new = len(new_text)
                delta = new - cur
                if n > hi and delta < 0 and n + delta >= lo and -delta > best_gain:
                    best, best_gain = (role, t), -delta
                elif n < lo and delta > 0 and n + delta <= hi and delta > best_gain:
                    best, best_gain = (role, t), delta
        if not best:
            break                          # 더 손댈 변형이 없다 — 게이트가 판정하게 둔다
        chosen[best[0]] = best[1]
    return _beats(), missing


def coverage(spine, slots):
    """이 재료로 이 스파인의 몇 칸을 채울 수 있나 — (채운 수, 전체 수, 못 채운 역할).
    화면이 "재료가 모자라다"를 **미리** 말해줄 수 있게 하는 값이다
    (생성을 돌린 뒤에 알면 사장님이 그만큼 기다린 뒤에 안다)."""
    roles = list((spine or {}).get("beat_roles") or [])
    beats, missing = fill(spine, slots)
    return len(beats), len(roles), missing


def _benefit_material_problem(slots, need, kind, why):
    """장점 나열로 굴러가는 갈래의 공용 자격 검사 → 못 쓰면 이유 문자열, 되면 ''.

    ★썰(오용형)과 자격이 다르다. 오용형은 "원래 용도를 뒤집는가"(`misuse_genre`)를 묻지만
      이 갈래들은 뒤집는 이야기가 아니다 — **뭐가 대단한가**다. 같은 검사를 재사용하면
      `misuse_genre=false`라 영영 막힌다(스파인은 있는데 죽어 있고 **오류도 안 난다**).

    ★**슬롯을 받는다**(2026-08-21 회귀로 고침). 처음엔 영상 재료(`sul_facts`)의
      `product_name`·`benefits`를 직접 봤는데, 은폐형은 {제품}·{효능}·{나라}를 **쿠팡
      재료에서도** 받는다(`slots_from_facts(product_facts, sul)`). 영상 쪽만 보면
      쿠팡으로 채워지는 소재를 통째로 막는다 — 실제로 회귀 테스트가 그걸 잡았다.
      슬롯은 두 재료를 합친 결과라, **템플릿이 실제로 쓰는 것**과 정확히 같다.

    `need` = 필요한 효능 칸 수. **템플릿이 요구하는 슬롯에서 나온 수다**(추측 금지):
      발명품형 3개 — benefit={효능} · escalate={효능2} · twist={효능3}
      은폐형   2개 — benefit={효능} · twist={효능2}   (효능3은 twist 변형에만 있어 선택)
    제품명은 둘 다 필수다(제목·정체공개가 {제품}을 쓴다).
    """
    sl = slots or {}
    if not str(sl.get("제품") or "").strip():
        return "제품명을 못 뽑았습니다(%s은 제목에 제품명이 들어가야 합니다)" % kind
    have = sum(1 for k in ("효능", "효능2", "효능3") if str(sl.get(k) or "").strip())
    if have < need:
        return "장점이 %d개뿐입니다 — %s은 %s 총 %d개가 필요합니다" % (
            have, kind, why, need)
    return ""


def invention_material_problem(slots):
    """발명품형(spine "유튜브 발명품형") 자격. 효능 3칸 + 제품명.

    {계기}는 **필수가 아니다** — 없으면 계기를 안 쓰는 story 변형이 대신 걸린다
    (없는 미담을 지어내는 것보다 그게 낫다).
    """
    return _benefit_material_problem(
        slots, 3, "발명품형", "핵심기능·고조·반전에 각각 하나씩")


def conceal_material_problem(slots):
    """은폐형(spine "유튜브 은폐형") 자격. 효능 2칸 + 제품명.

    ★라이브 spine 55의 templates에서 센 수다: reveal={제품} · benefit={효능} ·
      twist={효능2}. {효능3}은 twist 변형 3개 중 하나에만 있어 없어도 칸이 찬다.
      {나라}·{제품군}도 없는 변형이 있어 필수가 아니다.
    """
    return _benefit_material_problem(
        slots, 2, "은폐형", "핵심효능·반전에 각각 하나씩")


def sul_material_problem(sul):
    """이 재료로 오용형 대본을 쓸 수 있나 — 못 쓰면 **이유 문자열**, 되면 ''.

    ★슬롯이 차는 것과 **쓸 만한 것**은 다르다(2026-08-19 사장님 제보로 드러났다).
      마커펜 영상으로 조립했더니 이렇게 나왔다:
        "이게 원래는 필기구로 개발된 마카였음"          ← 원래 용도 = 제품 자체(뒤집을 게 없다)
        "초보들은 기껏해야 돌맹이 위에 그림 그리기"      ← 펜을 펜으로 쓰는 것
        "근데 미친 사용법은 … 자녀 필통에 선물로 넣어주기"  ← 하나도 안 놀랍다
      틀은 완벽히 지켜졌는데 **재료가 오용형이 아니어서** 대본이 공허했다.
      값이 차 있기만 하면 통과시키던 게 원인이다.

    여기서 잡는 것은 **기계가 확실히 판정할 수 있는 것만**이다("놀라운가"는 못 잰다):
      1) 원래 용도가 제품/제품군 이름과 사실상 같다 = 동어반복
      2) 엉뚱한 용도가 원래 용도와 사실상 같다 = 그냥 정상 사용
      3) 엉뚱한 용도가 2개 미만 = 대비도 반전도 못 만든다
    나머지(정말 놀라운가)는 `sul_facts` 프롬프트가 빈 배열로 두게 지시한다.
    """
    sf_ = sul or {}
    orig = [str(x).strip() for x in (sf_.get("original_use") or []) if str(x).strip()]
    mis = [str(x).strip() for x in (sf_.get("misuses") or []) if str(x).strip()]
    cat = str(sf_.get("category_word") or "").strip()

    # ★가장 확실한 신호 — 재료를 뽑은 그 모델이 "이 영상이 오용형인가"를 직접 답한다.
    #   문자열 규칙으로는 '필기구 ↔ 마카' 같은 동어반복을 못 잡는다(실측). 의미 판단은
    #   의미를 아는 쪽에 맡기고, 여기서는 그 답을 **믿되 확인 가능한 것만 덧붙여** 본다.
    if "misuse_genre" in sf_ and not sf_.get("misuse_genre"):
        return "이 영상은 '원래 용도를 뒤집는' 오용형이 아닙니다(제품 소개·사용법 안내)"
    if len(mis) < 2:
        return "이 영상엔 '엉뚱한 사용법'이 %d개뿐이라 오용형 대본이 안 나옵니다" % len(mis)
    if orig and cat and _same_thing(orig[0], cat):
        return ("원래 용도(%s)가 제품군(%s)과 같은 말이라 뒤집을 게 없습니다" % (orig[0], cat))
    if orig and any(_same_thing(orig[0], m) for m in mis):
        return "엉뚱한 사용법이 원래 용도와 같은 얘기입니다(그냥 정상 사용)"
    return ""


def _same_thing(a, b):
    """두 짧은 구가 사실상 같은 말인가 — 한쪽이 다른 쪽에 통째로 들어있으면 같다고 본다.
    (형태소 분석 없이 확실한 것만 잡는다. 애매한 건 통과시킨다 — 오탐이 더 나쁘다)"""
    a, b = (a or "").replace(" ", ""), (b or "").replace(" ", "")
    if not a or not b:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 2 and short in long_


def build_draft(spine, slots, seconds=30, source_text=""):
    """슬롯 조립 → **생성기와 같은 모양**의 대본 1안. 못 채우는 칸이 있으면 None.

    ★같은 모양으로 돌려주는 이유: 화면·게이트·저장이 이미 이 모양을 다룬다
      (`script_generate.generate_one_style` 반환형). 새 모양을 만들면 화면 코드가
      두 갈래가 되고, 두 갈래는 언젠가 어긋난다(0순위-B).

    ★칸이 하나라도 비면 아예 None을 돌려준다 — 반쪽 대본을 성공인 척 내놓는 게
      제일 나쁘다(`generate_one_style`이 같은 원칙을 쓴다: 중괄호가 남았거나 한 칸이
      전체를 삼킨 결과는 실패로 돌려보낸다).
    """
    from shopping_shorts import script_gate
    beats, missing = fill(spine, slots, seconds=seconds)
    if missing or not beats:
        return None
    script = " ".join(b["text"] for b in beats)
    # ★수치 근거 검사를 조립 경로에도 건다(2026-08-21). 종전엔 facts_text를 안 넘겨
    #   `grounding_check`가 통째로 건너뛰어졌다 — 생성기 경로만 검사받고 조립은 무검사였다.
    #
    #   ⚠️재료는 **원본 전사**여야 한다. 처음엔 슬롯 값들을 재료로 넘겼는데 그건
    #     **자기 자신과 대조**하는 꼴이라 무엇을 넣어도 통과했다(실측: 효과 슬롯에
    #     "체취의 53%"를 일부러 심었는데 '수치 근거 OK'가 나왔다). 검사가 있는 척만 하는
    #     배선은 없느니만 못하다 — 있는데 안 걸리는 판정이 가격 칸 사고의 뿌리였다.
    #   → 호출부가 source_text(담긴 영상 전사)를 넘겨야 진짜 검사가 된다. 안 넘기면
    #     종전과 같이 검사를 건너뛴다(오탐으로 정상 대본을 막지 않는다).
    checks, _full = script_gate.check(spine, beats, seconds=seconds,
                                      facts_text=(source_text or ""))
    return {
        "beats": beats,
        "script": script,
        "hook": beats[0]["text"],
        "checks": checks,
        "passed": script_gate.passed(checks),
        "tries": 0,
        "style_id": spine.get("id"),
        "style_name": spine.get("name") or "",
        # ★어느 경로로 만든 대본인지 **화면이 말할 수 있게** 표시한다.
        #   조용한 폴백이 쳇바퀴의 뿌리였다(memory: reference_silent_fallback_pipeline_undo).
        "made_by": "조립",
    }
