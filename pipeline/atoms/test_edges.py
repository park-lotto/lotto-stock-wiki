import pipeline.atoms.db as db_module
import pipeline.atoms.edges as edges


def _use_tmp(tmp_path, monkeypatch):
    p = tmp_path / "atoms.db"
    monkeypatch.setattr(db_module, "DB_PATH", p)
    db_module.init_db()
    edges.init_edges()


def test_insert_and_query_sector_members(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    edges.insert_edge("가온칩스", "반도체", "sector_member", "sector_map")
    edges.insert_edge("SK하이닉스", "반도체", "sector_member", "sector_map")
    edges.insert_edge("에코프로", "2차전지", "sector_member", "sector_map")
    members = edges.assets_in_sector("반도체")
    assert set(members) == {"가온칩스", "SK하이닉스"}
    assert edges.sectors_of_asset("가온칩스") == ["반도체"]


def test_query_empty_sector_returns_empty(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    assert edges.assets_in_sector("없는섹터") == []


def test_insert_edge_is_idempotent(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    edges.insert_edge("가온칩스", "반도체", "sector_member", "sector_map")
    edges.insert_edge("가온칩스", "반도체", "sector_member", "sector_map")
    assert edges.assets_in_sector("반도체") == ["가온칩스"]  # 중복 삽입 무시


def test_related_assets_two_hop(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    edges.insert_edge("가온칩스", "반도체", "sector_member", "sector_map")
    edges.insert_edge("SK하이닉스", "반도체", "sector_member", "sector_map")
    edges.insert_edge("엔비디아", "반도체", "foreign_sector", "foreign_map")
    edges.insert_edge("에코프로", "2차전지", "sector_member", "sector_map")
    rel = edges.related_assets("가온칩스")  # 반도체 동종, 자기 자신 제외
    assert set(rel) == {"SK하이닉스", "엔비디아"}
    assert edges.related_assets("고립주") == []  # 섹터 미등록 → 관련 없음


def test_seed_sector_edges(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    n = edges.seed_sector_edges(
        stock_sector_map={"가온칩스": "반도체", "에코프로": ["2차전지"]},
        foreign_sector_map={"엔비디아": ["반도체"]})
    assert n == 3
    assert set(edges.assets_in_sector("반도체")) == {"가온칩스", "엔비디아"}
    assert edges.assets_in_sector("2차전지") == ["에코프로"]
