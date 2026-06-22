"""검증게이트: certainty·신뢰도→등급, auto/staging 라우팅.

원칙(개정): '저신뢰=숨김'이 아니라 '저신뢰=반영하되 등급표기'.
일별 흐름을 위키에 담되 검증등급(⚠️미검증/설)을 붙인다.
staging은 **고위험 주장(파트너십·납품·M&A 등)** 만 — 교차확인 전까지 보류.
"""

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

    # 고위험 주장만 staging (교차확인 전까지). 등급은 보존.
    if high_risk:
        return {"grade": _GRADE_BY_CERTAINTY.get(cert, "미검증"), "route": "staging", "high_risk": True}
    # report(A)는 검증완료로 자동 반영 (스펙 §4.3)
    if trust == "A":
        return {"grade": "검증완료", "route": "auto", "high_risk": False}
    # 그 외 저신뢰(텔레·뉴스·블로그)도 위키에 반영하되 등급 표기 → auto
    return {"grade": _GRADE_BY_CERTAINTY.get(cert, "미검증"), "route": "auto", "high_risk": False}
