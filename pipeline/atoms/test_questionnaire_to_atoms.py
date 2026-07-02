import json
from pathlib import Path
from pipeline.atoms.questionnaire import questionnaire_to_atoms

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "spike_out.json").read_text(encoding="utf-8")
)
META = {"date": "2026-06-19", "broker": "테스트", "raw_file": "x.md"}


def _result_for(idx):
    return FIX[idx]["result"]


def test_stock_report_makes_one_atom_per_stock():
    atoms = questionnaire_to_atoms(_result_for(0), META)  # 현대차/기아
    assets = {a["asset"] for a in atoms}
    assert "현대차" in assets and "기아" in assets
    for a in atoms:
        assert a["asset_level"] == "stock"
        assert a["strength_score"] >= 3  # 목표가 동반 = 강한 신호


def test_sector_report_fans_out_korean_picks_only():
    atoms = questionnaire_to_atoms(_result_for(1), META)  # MLCC, picks 5개(해외 포함)
    levels = [a["asset_level"] for a in atoms]
    assert "sector" in levels  # 섹터 대표 원자 1개
    stock_assets = {a["asset"] for a in atoms if a["asset_level"] == "stock"}
    assert "삼성전기" in stock_assets       # 한국 상장사 → 포함
    assert "Murata" not in stock_assets     # 해외 → 제외
    for a in atoms:
        if a["asset_level"] == "stock":
            assert a["strength_score"] <= 2  # 거론 레벨 = 약한 신호


def test_report_stock_uses_sector_hint():
    q = {"target_kind": "stock", "stocks": [
        {"name": "삼성전자", "rating": "BUY", "tp_new": "100000",
         "tp_direction": "up", "sector": "반도체", "quote": "q"}]}
    meta = {"date": "2026-06-21", "broker": "테스트", "raw_file": "x.md"}
    atoms = questionnaire_to_atoms(q, meta)
    sams = [a for a in atoms if a["asset"] == "삼성전자"]
    assert sams and sams[0]["sector"] == "반도체"  # 기타 아님


def test_report_stock_no_hint_falls_back_to_기타():
    q = {"target_kind": "stock", "stocks": [
        {"name": "삼성전자", "rating": "BUY", "tp_new": "100000",
         "tp_direction": "up", "quote": "q"}]}
    meta = {"date": "2026-06-21", "broker": "테스트", "raw_file": "x.md"}
    atoms = questionnaire_to_atoms(q, meta)
    sams = [a for a in atoms if a["asset"] == "삼성전자"]
    assert sams and sams[0]["sector"] == "기타"  # hint 없으면 기타 fallback


def test_market_report_fans_out_sectors_and_picks():
    atoms = questionnaire_to_atoms(_result_for(2), META)  # 로봇/방산/조선 데일리
    sectors = {a["sector"] for a in atoms if a["asset_level"] == "sector"}
    assert {"로봇", "방산", "조선"} & sectors
    # 실제 픽스처 top_picks에서 is_korean_stock=True인 종목 (삼성전자는 픽스처에 없음)
    stock_assets = {a["asset"] for a in atoms if a["asset_level"] == "stock"}
    # 픽스처의 한국 상장 top_picks 중 하나 이상 포함되어야 함
    korean_picks_in_fixture = {"레인보우로보틱스", "한화에어로스페이스", "삼성중공업", "HD현대중공업"}
    assert stock_assets & korean_picks_in_fixture, (
        f"한국 상장 종목이 atoms에 없음. stock_assets={stock_assets}"
    )
    assert any(a["asset_level"] == "market" for a in atoms)


def test_stock_report_populates_structured_fields():
    import json
    atoms = questionnaire_to_atoms(_result_for(0), META)  # 현대차/기아
    stock_atoms = [a for a in atoms if a["asset_level"] == "stock"]
    assert stock_atoms
    sf = json.loads(stock_atoms[0]["structured_fields"])
    assert "rating" in sf and "tp_new" in sf and "thesis" in sf


def test_sector_report_populates_structured_fields():
    import json
    atoms = questionnaire_to_atoms(_result_for(1), META)  # MLCC
    sec_atoms = [a for a in atoms if a["asset_level"] == "sector"]
    assert sec_atoms
    sf = json.loads(sec_atoms[0]["structured_fields"])
    assert "sector_view" in sf and "top_picks" in sf


def test_market_report_populates_structured_fields():
    import json
    atoms = questionnaire_to_atoms(_result_for(2), META)  # 로봇/방산/조선 데일리
    mkt_atoms = [a for a in atoms if a["asset_level"] == "market"]
    assert mkt_atoms
    sf = json.loads(mkt_atoms[0]["structured_fields"])
    assert "market_direction" in sf and "recommended_sectors" in sf


def test_stock_report_survives_dict_shaped_earnings_outlook():
    """Gemini가 earnings_outlook/thesis 슬롯에 문자열 대신 dict/list-of-dict를
    채워 넣어도(2026-07-02 실제 발생) TypeError 없이 content로 합쳐져야 한다."""
    q = {"target_kind": "stock", "stocks": [
        {"name": "삼성전자", "rating": "BUY", "tp_new": "100000",
         "tp_direction": "up", "quote": "q",
         "earnings_outlook": {"summary": "실적 개선", "detail": "메모리 가격 상승"},
         "thesis": ["단순 문자열", {"point": "구조화된 항목"}]}]}
    meta = {"date": "2026-07-02", "broker": "테스트", "raw_file": "x.md"}
    atoms = questionnaire_to_atoms(q, meta)
    sams = [a for a in atoms if a["asset"] == "삼성전자"]
    assert sams
    content = sams[0]["content"]
    assert "실적 개선" in content
    assert "구조화된 항목" in content
