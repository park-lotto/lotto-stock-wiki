from pipeline.atoms.sector_classify import sectors_list, resolve_sector


def test_sectors_list_loads():
    s = sectors_list()
    assert "반도체" in s and "양자보안" in s and "기타" in s


def test_korean_uses_hint():
    # 한국주: 오버라이드 map 안 봄, hint 그대로
    secs, src = resolve_sector("삼성전자", "반도체", is_foreign=False)
    assert secs == ["반도체"]
    assert src == "gemini"


def test_foreign_map_overrides_hint():
    # 애플: foreign map [반도체,IT]가 hint보다 우선
    secs, src = resolve_sector("애플", "IT", is_foreign=True)
    assert secs == ["반도체", "IT"]
    assert src == "map"


def test_foreign_unmapped_uses_hint():
    # 모르는 외국주: map 없으면 hint로 살림 (코멘트 손실 방지)
    secs, src = resolve_sector("ZZZChip", "반도체", is_foreign=True)
    assert secs == ["반도체"]
    assert src == "gemini"


def test_hint_partial_match_normalized():
    # "반도체장비" → 부분매칭 → 반도체
    secs, src = resolve_sector("어떤외국주", "반도체장비", is_foreign=True)
    assert secs == ["반도체"]
    assert src == "gemini_norm"


def test_no_hint_falls_back():
    secs, src = resolve_sector("ZZZChip", None, is_foreign=True)
    assert secs == ["기타"]
    assert src == "fallback"


def test_hint_off_taxonomy_falls_back():
    # 목록에도 부분매칭도 안 되는 값
    secs, src = resolve_sector("X", "완전이상한섹터명123", is_foreign=False)
    assert secs == ["기타"]
    assert src == "fallback"
