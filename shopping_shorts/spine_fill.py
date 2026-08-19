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
SLOT_NAMES = ("제품", "효능", "효능2", "나라", "본래용도", "속성",
              "용도", "용도2", "용도3", "용도끝", "용도들", "제품군")

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
    out = {
        "제품": _first(pf.get("title")),
        "효능": _first(why[0]) if len(why) > 0 else "",
        "효능2": _first(why[1]) if len(why) > 1 else "",
        "나라": _first(pf.get("origin")),
        "본래용도": _first(sf.get("original_use")),
        "속성": _first(sf.get("hidden_property")),
        "용도": _first(sf.get("misuses")),
        # ★twist는 cases에서 이미 말한 것을 또 말하면 안 된다(실측: 둘 다 '인테리어
        #   소품'이 나와 반전이 죽었다). 사례가 여럿이면 **마지막 것**을 반전에 쓴다.
        # ★실측 대본의 cases는 명사 나열이 아니라 **초보 vs 고수 대비**다
        #   ("초보 주부들은 기껏해야 환기 정도가 전부였음 / 하지만 고수 주부들은
        #     주방 벽에 설치해서 시원하게 요리한다고"). 그래서 두 번째 사례가 필요하다.
        "용도2": _nth(sf.get("misuses"), 1),
        # 고조 연결어('심지어')를 받는 세 번째 사례. 실측 대본에 그대로 있다
        #   ("…걸어버리면서 심지어 물티슈까지 걸어두고"). 게이트도 고조 1회를 요구한다.
        "용도3": _nth(sf.get("misuses"), 2),
        "용도끝": _last(sf.get("misuses")),
        "용도들": _join_cases(sf.get("misuses")),
        "제품군": _first(sf.get("category_word")),
    }
    return {k: v for k, v in out.items() if v}


def pick_template(templates, slots):
    """이 역할의 후보 문장들 중 **슬롯이 전부 채워지는 첫 번째**를 고른다.

    ★고르는 규칙이 곧 품질이다: 슬롯이 하나라도 비면 그 문장은 쓰지 않는다.
      대신 슬롯이 더 적은 변형이 있으면 그게 걸린다(그래서 변형을 여러 개 둔다).
      실측 예: bait 변형 3개 중 하나는 {제품군}을 요구하고 둘은 슬롯이 없다 —
      제품군을 못 뽑은 영상에서도 미끼 문장은 나온다.
    """
    for t in (templates or []):
        need = slots_in(t)
        if any(n not in SLOT_NAMES for n in need):
            continue                       # 모르는 슬롯이 있는 템플릿은 건너뛴다
        if all(slots.get(n) for n in need):
            return t
    return ""


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


def fill(spine, slots):
    """스파인 + 슬롯 → (beats, missing)

    beats  = [{"role": ..., "text": ...}]  — 채워진 칸만. **한 칸에 한 문장**이다.
    missing= 슬롯이 모자라 못 채운 역할들(호출부가 모델에 맡기거나 재료를 더 뽑는다).

    ★CTA가 붙을 자리가 없다 — 템플릿에 없으면 나올 수 없다. 그게 이 방식의 요점이다.
    """
    roles = list((spine or {}).get("beat_roles") or [])
    templates = (spine or {}).get("templates") or {}
    beats, missing = [], []
    for role in roles:
        t = pick_template(templates.get(role), slots)
        if not t:
            missing.append(role)
            continue
        text = fill_one(t, slots)
        if text:
            beats.append({"role": role, "text": text})
        else:
            missing.append(role)
    return beats, missing


def coverage(spine, slots):
    """이 재료로 이 스파인의 몇 칸을 채울 수 있나 — (채운 수, 전체 수, 못 채운 역할).
    화면이 "재료가 모자라다"를 **미리** 말해줄 수 있게 하는 값이다
    (생성을 돌린 뒤에 알면 사장님이 그만큼 기다린 뒤에 안다)."""
    roles = list((spine or {}).get("beat_roles") or [])
    beats, missing = fill(spine, slots)
    return len(beats), len(roles), missing
