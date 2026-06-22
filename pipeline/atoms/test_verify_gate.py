from pipeline.atoms.verify_gate import grade

def test_report_A_auto_verified():
    g = grade({"source_trust": "A", "certainty": "사실", "content": "TP 상향"})
    assert g["grade"] == "검증완료" and g["route"] == "auto"

def test_telegram_rumor_auto_tagged():
    # 저신뢰 소문도 위키에 반영하되 '설' 등급 표기 (숨기지 않음)
    g = grade({"source_trust": "C", "certainty": "단독설", "content": "테슬라 회동 관측"})
    assert g["grade"] == "설" and g["route"] == "auto"

def test_telegram_fact_auto_unverified():
    # 텔레 일반 정보 → auto, 미검증 등급
    g = grade({"source_trust": "C", "certainty": "불명", "content": "2nm 수율 50% 달성"})
    assert g["route"] == "auto" and g["grade"] == "미검증"

def test_high_risk_claim_flagged():
    # 고위험 주장(납품·계약 등)만 staging — 교차확인 전까지
    g = grade({"source_trust": "C", "certainty": "관측", "content": "삼성과 납품 계약 체결"})
    assert g["high_risk"] is True and g["route"] == "staging"

def test_report_A_unknown_certainty_still_auto():
    # certainty 미주입(불명)이어도 report A는 자동 (스펙 §4.3)
    g = grade({"source_trust": "A", "certainty": "불명", "content": "실적 호조"})
    assert g["route"] == "auto" and g["grade"] == "검증완료"

def test_high_risk_report_A_still_staged():
    g = grade({"source_trust": "A", "certainty": "사실", "content": "대규모 납품 계약 체결"})
    assert g["route"] == "staging" and g["high_risk"] is True
