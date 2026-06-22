from pipeline.atoms.verify_gate import grade

def test_report_A_auto_verified():
    g = grade({"source_trust": "A", "certainty": "사실", "content": "TP 상향"})
    assert g["grade"] == "검증완료" and g["route"] == "auto"

def test_telegram_rumor_staged():
    g = grade({"source_trust": "C", "certainty": "단독설", "content": "최태원 머스크 회동 예정"})
    assert g["grade"] == "설" and g["route"] == "staging"

def test_high_risk_claim_flagged():
    g = grade({"source_trust": "C", "certainty": "관측", "content": "삼성과 납품 계약 체결"})
    assert g["high_risk"] is True and g["route"] == "staging"
