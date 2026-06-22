"""검증게이트: certainty·신뢰도→등급, auto/staging 라우팅. 설계 §4.3."""

_HIGH_RISK = ("파트너십", "납품", "인수", "수주", "계약", "합병", "M&A")
_GRADE_BY_CERTAINTY = {
    "사실": "검증완료", "관측": "미검증", "전망": "미검증",
    "단독설": "설", "불명": "미검증",
}


def grade(atom: dict) -> dict:
    trust = atom.get("source_trust", "D")
    cert = atom.get("certainty", "불명")
    content = atom.get("content", "")
    high_risk = any(k in content for k in _HIGH_RISK)

    g = _GRADE_BY_CERTAINTY.get(cert, "미검증")
    # report A + 사실 → 자동 검증완료 (단 고위험은 여전히 확인)
    if trust == "A" and cert == "사실" and not high_risk:
        return {"grade": "검증완료", "route": "auto", "high_risk": False}
    if high_risk:
        return {"grade": g, "route": "staging", "high_risk": True}
    if g == "검증완료":  # A 아닌데 사실 주장 → 신뢰도 따라
        route = "auto" if trust in ("A", "B") else "staging"
        return {"grade": g, "route": route, "high_risk": False}
    return {"grade": g, "route": "staging", "high_risk": False}
