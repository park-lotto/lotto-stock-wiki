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

    # 고위험 주장은 신뢰도 무관하게 staging (교차확인 전까지)
    if high_risk:
        return {"grade": _GRADE_BY_CERTAINTY.get(cert, "미검증"), "route": "staging", "high_risk": True}
    # report(A)는 자동 검증완료 (스펙 §4.3) — certainty 미주입이어도 리포트는 검증된 사실
    if trust == "A":
        return {"grade": "검증완료", "route": "auto", "high_risk": False}
    g = _GRADE_BY_CERTAINTY.get(cert, "미검증")
    if g == "검증완료":  # A 아닌데 '사실' 주장 → B까지 auto
        route = "auto" if trust == "B" else "staging"
        return {"grade": g, "route": route, "high_risk": False}
    return {"grade": g, "route": "staging", "high_risk": False}
