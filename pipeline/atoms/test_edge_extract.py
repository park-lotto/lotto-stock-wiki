import pipeline.atoms.db as db_module
import pipeline.atoms.edges as edges
import pipeline.atoms.edge_extract as ee


def test_parse_valid_edges():
    txt = '[{"src":"삼성전자","dst":"가온칩스","type":"customer","confidence":0.9}]'
    out = ee.parse_edges_response(txt, "atom1")
    assert len(out) == 1
    assert out[0]["src"] == "삼성전자"
    assert out[0]["relation_type"] == "customer"
    assert out[0]["source_atom_id"] == "atom1"
    assert out[0]["confidence"] == 0.9


def test_parse_json_fenced():
    txt = '```json\n[{"src":"A","dst":"B","type":"supply"}]\n```'
    out = ee.parse_edges_response(txt, "a2")
    assert len(out) == 1
    assert out[0]["confidence"] == 0.5  # 누락 시 기본값


def test_parse_rejects_invalid_type_and_self_loop():
    txt = '[{"src":"A","dst":"B","type":"friends"},{"src":"C","dst":"C","type":"supply"}]'
    assert ee.parse_edges_response(txt, "a3") == []


def test_parse_malformed_returns_empty():
    assert ee.parse_edges_response("not json at all", "a4") == []
    assert ee.parse_edges_response("", "a5") == []
    assert ee.parse_edges_response("{}", "a6") == []  # dict(배열 아님) → []


def test_extract_from_atom_uses_generate_fn():
    atom = {"id": "x1", "content": "삼성전자가 가온칩스에 물량 발주"}
    fake = lambda p: '[{"src":"삼성전자","dst":"가온칩스","type":"customer","confidence":0.8}]'
    out = ee.extract_edges_from_atom(atom, generate_fn=fake)
    assert out[0]["source_atom_id"] == "x1"
    assert out[0]["dst"] == "가온칩스"


def test_extract_empty_content_returns_empty():
    assert ee.extract_edges_from_atom({"id": "y", "content": ""}, generate_fn=lambda p: "x") == []


def test_run_extraction_inserts_edges(tmp_path, monkeypatch):
    p = tmp_path / "atoms.db"
    monkeypatch.setattr(db_module, "DB_PATH", p)
    db_module.init_db()
    edges.init_edges()
    db_module.insert_atom({
        "id": "a1", "date": "2026-07-06", "source_type": "news", "source_name": "N",
        "source_trust": "B", "raw_file": None, "layer": None, "sector": "반도체",
        "asset": "삼성전자", "asset_level": "stock", "signal": "bullish",
        "event_type": "news", "magnitude": "major", "content_type": "fact",
        "strength_score": 3, "validity_type": "permanent", "validity_until": None,
        "is_active": 1, "content": "삼성전자가 가온칩스에 발주", "relations": []})
    fake = lambda p: '[{"src":"삼성전자","dst":"가온칩스","type":"customer","confidence":0.9}]'
    n = ee.run_extraction(days=30, limit=10, generate_fn=fake)
    assert n == 1
    # 엣지가 실제로 조회되고 근거원자가 붙는지
    assert "삼성전자" in edges.assets_in_sector("가온칩스") or edges.sectors_of_asset("삼성전자") == ["가온칩스"]
