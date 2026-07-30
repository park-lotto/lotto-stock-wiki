"""대화체 스코어러(A3, Phase2 부품) — 요약체·AI냄새를 결정적으로 반려.
1차 규칙기반(무과금): 문어체 종결어미(narration_naturalize._SPOKEN_MAP 재사용) +
어미 다양성 + 승인 코퍼스 어미 매칭 보너스. 경계선 점수만 Gemini(call 주입).
사전을 손으로 만들지 않는다 — 승인 데이터가 곧 사전(approved_endings)."""
import re

from shopping_shorts import narration_naturalize

# 문어체(요약체) 종결어미 = narration_naturalize 매핑의 좌변 재사용(사전 손수 안 만듦)
_FORMAL_ENDERS = [a for a, _ in narration_naturalize._SPOKEN_MAP]

# AI냄새/요약체 시드(F5 네거티브뱅크가 곧 확장) — 오늘 비교분석 실패사례.
_AI_SMELL = ["확인하셨어요", "너무 좋아합니다", "많은 분들이", "추천드립니다"]

_BORDERLINE = (0.4, 0.7)  # 이 밴드면 Gemini 재판(call 있을 때만)


def _sentences(text):
    return [s.strip() for s in re.split(r"[.!?\n]+", text or "") if s.strip()]


def _clean(sentence):
    return re.sub(r"[^가-힣]", "", sentence)


def _ending(sentence, n=2):
    s = _clean(sentence)
    return s[-n:] if len(s) >= n else s


# ── 어미 '유형' 판정(2026-07-30 v2) ─────────────────────────────────────
# ★왜 유형인가: 예전 ending_diversity는 **끝 2음절**의 고유비율이었다. 그래서
#   "마세요/있네요/물어봤어요/방향제래요/재밌었어요/써요/남겨주세요"처럼 **전부 '~요'로
#   끝나는** 대본이 세요·네요·어요·래요·써요 = 5종으로 세어져 0.71 → 임계 0.5를 통과했다.
#   사장님이 "다 ~했어요로 끊긴다"고 느끼는 그 단조로움을 지표가 구조적으로 못 잡은 것.
#   → 표면 음절이 아니라 **말맛의 종류**로 묶는다. 'LIVE(썰 푸는 구어)'가 몇 개인지,
#     'PLAIN(밋밋한 평서)'이 과반인지가 실제 체감과 맞는 축이다.
# 순서 중요: 먼저 매칭되는 것이 이긴다(긴 어미가 앞).
_ENDING_TYPES = [
    # LIVE — 옆에서 썰 푸는 구어체(사장님이 원하는 말맛). 여기 없는 걸 추가할 땐 실제 대본에서
    # 관측된 것만 넣는다(사전을 상상으로 불리지 않는다).
    # ⚠️ '~는 거 있죠'는 QUESTION으로 잡히게 여기 넣지 않는다(둘 다 _LIVELY라 말맛 집계는 동일,
    #    대신 유형이 갈려 다양성이 제대로 측정된다).
    ("LIVE", ["더라니까요", "더라구요", "더라고요", "드라고요", "거든요", "잖아요",
              "던데요", "는데요", "은데요", "라지뭐예요", "라지뭐야", "라니까요",
              "더니", "라는거예요", "는거예요", "은거예요"]),
    # QUESTION — 되묻기(있죠?·않나요?·까요?). 몰입을 주는 축이라 LIVE와 별개 유형.
    ("QUESTION", ["있죠", "않나요", "까요", "나요", "죠"]),
    # IMPERATIVE — 훅·CTA의 명령/권유(마세요·해보세요).
    ("IMPERATIVE", ["마세요", "주세요", "보세요", "하세요", "세요"]),
    # PLAIN — 밋밋한 평서 종결. 이게 과반이면 광고 문구처럼 들린다.
    ("PLAIN", ["했어요", "됐어요", "왔어요", "봤어요", "네요", "어요", "아요", "해요",
               "예요", "이에요", "래요", "대요", "군요", "습니다", "입니다", "ㅂ니다"]),
]
_LIVELY = ("LIVE", "QUESTION")


def ending_type(sentence):
    """문장 하나의 종결어미 유형 → 'LIVE'|'QUESTION'|'IMPERATIVE'|'PLAIN'|'NOMINAL'.
    어느 패턴에도 안 걸리면 NOMINAL(명사·체언 종결 등)."""
    s = _clean(sentence)
    if not s:
        return "NOMINAL"
    for name, pats in _ENDING_TYPES:
        if any(s.endswith(p) for p in pats):
            return name
    # 폴백: 위 목록에 없는 '~요/~다' 종결은 전부 밋밋한 평서로 본다.
    # ★없으면 '써요'처럼 목록에 빠진 어미가 NOMINAL로 새서 단조로운 대본이 '다양하다'고
    #   판정된다(실측: 전부 ~요인 대본이 0.5로 임계를 아슬하게 통과했다).
    if s.endswith(("요", "다")):
        return "PLAIN"
    return "NOMINAL"


def ending_profile(text):
    """대본 전체의 어미 분포 → {types, diversity, live_ratio, plain_ratio, n}.

    diversity: 어미 **유형**의 고유비율(0~1). 표면 음절이 아니라 말맛 종류 기준.
    live_ratio: LIVE+QUESTION 비율(사장님이 원하는 '썰 푸는' 어미가 얼마나 있나).
    plain_ratio: PLAIN 비율(밋밋한 평서가 과반이면 광고처럼 들린다)."""
    sents = _sentences(text)
    n = len(sents)
    if not n:
        return {"types": [], "diversity": 1.0, "live_ratio": 0.0, "plain_ratio": 0.0, "n": 0}
    types = [ending_type(s) for s in sents]
    live = sum(1 for t in types if t in _LIVELY)
    plain = sum(1 for t in types if t == "PLAIN")
    # ★분모는 n이 아니라 min(n, 유형 총수)다. 유형은 5종뿐이라 n으로 나누면 문장이 많을수록
    #   좋은 대본도 자동으로 낮아진다(7문장이면 아무리 잘 써도 최대 0.71). '몇 종류를 썼나'를
    #   물어야지 '문장마다 다른 종류였나'를 물으면 안 된다.
    denom = min(n, 5)
    return {"types": types,
            "diversity": 1.0 if n <= 1 else len(set(types)) / denom,
            "live_ratio": live / n, "plain_ratio": plain / n, "n": n}


def ending_diversity(text):
    """문장 종결어미 **유형**의 고유비율(0~1). 문장 1개 이하면 1.0.

    ⚠️ v2(2026-07-30)부터 '끝 2음절'이 아니라 유형 기준이다 — 세요/네요/어요는 전부 서로
    다른 음절이지만 말맛으로는 명령 1종 + 평서 2종이라, 음절 기준은 단조로운 대본을
    '다양하다'고 판정했다(실측 0.71로 통과)."""
    return ending_profile(text)["diversity"]


# ── 감각어(2026-07-30 v2 사장님: "감각어를 풍부하게 표현해야 해") ────────────────
# 프롬프트는 07-29부터 "감각 형용사·생동감 부사를 써라"고 시켰는데 채점이 이걸 아예 안 봐서
# 실측 5건 중 형용사 0개짜리도 tone 1.00이었다(지시가 사실상 무시). 어미와 같은 방식으로
# **세어서 점수에 반영**한다.
# ⚠️ '너무·정말·진짜'는 감각어가 아니라 **강조어**다 — 실측에서 부사의 대부분이 이것이었다.
#    강조어는 가산에서 빼고, 감각어 없이 강조어만 많으면 오히려 밋밋함의 신호로 본다.
_SENSORY_WORDS = [
    # 식감·맛
    "쫀득", "꾸덕", "바삭", "촉촉", "폭신", "말랑", "보들보들", "부드러", "고소", "담백",
    "아삭", "쫄깃", "진하", "달큰", "새콤",
    # 촉감·온도·무게
    "시원", "따끈", "뜨끈", "포근", "묵직", "매끈", "까슬", "보송", "눅눅", "축축",
    # 후각
    "향긋", "은은", "상큼", "꿉꿉", "쿰쿰", "꼬릿", "퀴퀴",
    # 시각
    "반짝", "뽀얀", "노릇", "소복", "깜찍", "새하얀", "샛노란",
    # 의태·의성(동작이 눈에 그려지는 말)
    "뚝딱", "뻘뻘", "꽁꽁", "사르르", "보글보글", "지글지글", "후루룩", "스르륵",
    "순식간", "바짝", "한가득", "소복소복", "촤르르", "톡톡", "쓱쓱",
]
# 1음절 의태어 — 부분일치하면 오탐(확인·싹둑·팍팍한…)이라 앞뒤 경계를 본다.
_SENSORY_SHORT = ["확", "싹", "쓱", "팍", "쭉", "훅", "푹", "쫙"]
# 감각어가 아니라 그냥 세기를 올리는 말. 남발하면 오히려 광고 문투다.
_INTENSIFIERS = ["너무", "정말", "진짜", "완전", "엄청", "아주", "매우", "되게", "굉장히"]


def sensory_profile(text):
    """감각어 밀도 → {hits, count, per100, intensifiers}.

    count: 감각 형용사·의태어 **고유** 개수(같은 말 반복은 1로 센다 — 반복은 풍부함이 아니다).
    per100: 공백 제외 100자당 감각어 수(길이가 다른 대본을 공평하게 비교).
    intensifiers: '너무·정말·진짜'류 총 등장수(감각어와 별개)."""
    t = text or ""
    hits = {w for w in _SENSORY_WORDS if w in t}
    for w in _SENSORY_SHORT:
        if re.search(r"(?:^|[\s,.!?\"'])" + w + r"(?=\s)", t):
            hits.add(w)
    body = len(re.sub(r"\s", "", t))
    inten = sum(t.count(w) for w in _INTENSIFIERS)
    return {"hits": sorted(hits), "count": len(hits),
            "per100": round(len(hits) / body * 100, 2) if body else 0.0,
            "intensifiers": inten}


# 재미강도(D14) — 강한 재미 장치. 일반 서술만이면 반려(재생성).
_DEVICE_MARKERS = {
    "before_after": ["예전엔", "예전에", "전에는", "전엔", "원래", "이제는", "이젠", "바뀌", "달라졌", "옛날엔"],
    "반전": ["근데", "알고보니", "사실은", "반전", "의외로", "놀랍게도", "그런데 이게", "웬걸"],
    "극적대비": ["제일", "가장", "최고", "이것만", "딱 하나", "단 하나", "유일", "이거 하나로"],
    "손실회피": ["모르면 손해", "놓치면", "안 하면", "후회", "손해예요", "이것만은"],
}


def fun_intensity(text):
    """재미강도(D14): 강한 장치(비포애프터·반전·극적대비·손실회피)를 찾는다.
    → {devices:[found], has_strong:bool, needs_regen:bool}. 하나도 없으면 재생성 신호."""
    t = text or ""
    found = [k for k, kws in _DEVICE_MARKERS.items() if any(w in t for w in kws)]
    has = bool(found)
    return {"devices": found, "has_strong": has, "needs_regen": not has}


def score_conversational(text, approved_endings=None, negatives=None, call=None):
    """→ {score(0~1), flags:[...], needs_review:bool}. 높을수록 대화체(사람 같은)."""
    if not (text or "").strip():
        return {"score": 0.0, "flags": ["empty"], "needs_review": False}
    flags = []
    # ★가산과 감점을 따로 모은다(2026-07-30). 예전처럼 순서대로 더하고 빼면 가산이 감점을
    #   덮어써서 '감각어부족' 플래그가 뜬 후보도 1.00이 나왔다 — 점수가 1.0에 몰려
    #   추천이 다시 눈먼다. 가산은 1.0 천장까지만, 감점은 그 뒤에 반드시 물린다.
    score = 1.0
    bonus = 0.0
    # 1) 문어체 종결어미
    formal = sum(text.count(e) for e in _FORMAL_ENDERS)
    if formal:
        flags.append(f"문어체어미×{formal}")
        score -= min(0.5, 0.15 * formal)
    # 2) AI냄새/네거티브
    bad = list(_AI_SMELL) + list(negatives or [])
    hit = [b for b in bad if b and b in text]
    if hit:
        flags.append("AI냄새:" + ",".join(hit[:3]))
        score -= min(0.4, 0.2 * len(hit))
    # 3) 어미 — 유형 다양성 + 말맛(v2, 2026-07-30). 음절이 아니라 유형으로 본다.
    prof = ending_profile(text)
    div = prof["diversity"]
    if div < 0.5:
        flags.append(f"어미단조({div:.2f})")
        score -= (0.5 - div)
    # 3-a) 밋밋한 평서(PLAIN)가 과반이면 광고 문구처럼 들린다 — 프롬프트의 '절반 넘기지 마라'와 짝.
    if prof["n"] >= 3 and prof["plain_ratio"] > 0.5:
        flags.append(f"평서과다({prof['plain_ratio']:.2f})")
        score -= min(0.3, 0.6 * (prof["plain_ratio"] - 0.5))
    # 3-b) '썰 푸는' 어미(더라구요·있죠?·거든요…)가 하나도 없으면 사장님이 말한 그 밋밋함이다.
    #      있으면 소폭 가산 — 감점만 있으면 후보 전부 밋밋할 때 서로 구별이 안 된다(추천이 눈먼다).
    if prof["n"] >= 3:
        if prof["live_ratio"] == 0:
            flags.append("생생어미0")
            score -= 0.25
        else:
            bonus += min(0.15, 0.5 * prof["live_ratio"])
    # 3-c) 감각어 밀도(v2) — 오감 형용사·의태어가 장면을 눈앞에 그린다. 프롬프트가 요구하는
    #      바로 그것을 점수로도 본다(안 보면 지시가 무시된다: 실측 형용사 0개도 만점이었다).
    sens = sensory_profile(text)
    if len(_clean(text)) >= 40:            # 너무 짧은 텍스트엔 밀도를 묻지 않는다
        if sens["count"] == 0:
            flags.append("감각어0")
            score -= 0.2
        elif sens["per100"] < 1.5:         # 100자당 1.5개 미만 = 밋밋
            flags.append(f"감각어부족({sens['count']}개)")
            score -= 0.1
        else:
            bonus += min(0.15, 0.03 * sens["count"])
        # 감각어는 없는데 '너무·정말·진짜'만 반복 = 세기만 올린 광고 문투
        if sens["intensifiers"] >= 3 and sens["count"] < sens["intensifiers"]:
            flags.append(f"강조어남발({sens['intensifiers']})")
            score -= 0.1
    # 4) 승인 코퍼스 어미 매칭 보너스(사전=승인 데이터)
    if approved_endings:
        sents = _sentences(text)
        if sents:
            matched = sum(1 for s in sents
                          if any(_clean(s).endswith(e) for e in approved_endings if e))
            score += 0.1 * (matched / len(sents))
    # 가산 먼저 천장(1.0)까지 → 그 다음 감점. 감점이 항상 점수에 반영된다.
    score = max(0.0, min(1.0, 1.0 + bonus) - (1.0 - score))
    needs_review = _BORDERLINE[0] <= score <= _BORDERLINE[1]
    # 경계선이고 Gemini 있으면 재판(결정적 규칙을 못 가르는 애매한 경우만)
    if needs_review and call is not None:
        verdict = call(text)
        if isinstance(verdict, dict) and "score" in verdict:
            score = max(0.0, min(1.0, float(verdict["score"])))
            flags.append("gemini재판")
            needs_review = False
    return {"score": round(score, 3), "flags": flags, "needs_review": needs_review}
