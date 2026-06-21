from pipeline.atoms.codemap import code_for, is_korean_stock


def test_known_korean_stock_returns_code():
    # 삼성전기는 wisereport+KRX 양쪽에 모두 존재
    assert code_for("삼성전기") == "009150"


def test_foreign_name_returns_none():
    assert code_for("Murata") is None
    assert is_korean_stock("Murata") is False


def test_whitespace_tolerant():
    assert code_for("  삼성전기 ") == "009150"


def test_krx_coverage_두산로보틱스():
    # 두산로보틱스(454910) — wisereport에 없어 이전에 fan-out 드롭됐던 종목.
    # KRX 전종목 연동 후 인식돼야 함.
    assert is_korean_stock("두산로보틱스") is True
    assert code_for("두산로보틱스") == "454910"


def test_krx_coverage_hd현대중공업():
    # 현대중공업 → HD현대중공업으로 사명 변경. KRX 공식명으로 인식해야 함.
    assert is_korean_stock("HD현대중공업") is True
    assert code_for("HD현대중공업") == "329180"


def test_total_coverage():
    # KRX + wisereport 합산 2600종목 이상
    from pipeline.atoms.codemap import _CACHE, _ensure
    _ensure()
    assert len(_CACHE) >= 2600
