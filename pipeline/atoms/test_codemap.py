from pipeline.atoms.codemap import code_for, is_korean_stock

def test_known_korean_stock_returns_code():
    # 삼성전기는 wisereport에 반드시 존재 (2026-06 리포트 다수)
    assert code_for("삼성전기") == "009150"

def test_foreign_name_returns_none():
    assert code_for("Murata") is None
    assert is_korean_stock("Murata") is False

def test_whitespace_tolerant():
    assert code_for("  삼성전기 ") == "009150"
