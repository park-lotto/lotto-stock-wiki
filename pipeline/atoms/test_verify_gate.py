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

def test_report_A_unknown_certainty_still_auto():
    # certainty 미주입(불명)이어도 report A는 자동 (스펙 §4.3)
    g = grade({"source_trust": "A", "certainty": "불명", "content": "실적 호조"})
    assert g["route"] == "auto" and g["grade"] == "검증완료"

def test_high_risk_report_A_still_staged():
    g = grade({"source_trust": "A", "certainty": "사실", "content": "대규모 납품 계약 체결"})
    assert g["route"] == "staging" and g["high_risk"] is True
