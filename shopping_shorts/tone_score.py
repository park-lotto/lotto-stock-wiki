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


def ending_diversity(text):
    """문장 종결어미(끝 2음절)의 고유비율(0~1). 문장 1개 이하면 1.0."""
    sents = _sentences(text)
    if len(sents) <= 1:
        return 1.0
    ends = [_ending(s) for s in sents]
    return len(set(ends)) / len(ends)


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
    score = 1.0
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
    # 3) 어미 다양성
    div = ending_diversity(text)
    if div < 0.5:
        flags.append(f"어미단조({div:.2f})")
        score -= (0.5 - div)
    # 4) 승인 코퍼스 어미 매칭 보너스(사전=승인 데이터)
    if approved_endings:
        sents = _sentences(text)
        if sents:
            matched = sum(1 for s in sents
                          if any(_clean(s).endswith(e) for e in approved_endings if e))
            score += 0.1 * (matched / len(sents))
    score = max(0.0, min(1.0, score))
    needs_review = _BORDERLINE[0] <= score <= _BORDERLINE[1]
    # 경계선이고 Gemini 있으면 재판(결정적 규칙을 못 가르는 애매한 경우만)
    if needs_review and call is not None:
        verdict = call(text)
        if isinstance(verdict, dict) and "score" in verdict:
            score = max(0.0, min(1.0, float(verdict["score"])))
            flags.append("gemini재판")
            needs_review = False
    return {"score": round(score, 3), "flags": flags, "needs_review": needs_review}
