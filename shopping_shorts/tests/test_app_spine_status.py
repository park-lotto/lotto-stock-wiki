"""스파인 승인/기각 API + 승격게이트 필드 통합 테스트(큐레이션 UI 백엔드)."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_mod
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    return TestClient(app_mod.app), Store(db)


def test_spine_status_approve(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    sid = store.add_spine("제3자의심→인정", situation_type="레시피")
    r = client.post("/api/pattern/spine/status", json={"id": sid, "status": "approved"})
    assert r.status_code == 200 and r.json()["ok"] is True
    row = [s for s in store.list_spines() if s["id"] == sid][0]
    assert row["status"] == "approved"


def test_spine_status_requires_id_and_status(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/pattern/spine/status", json={"status": "approved"})
    assert r.status_code == 422


def test_spines_list_carries_gate_fields(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    sid = store.add_spine("아크A", situation_type="뷰티")
    store.update_spine_stats(sid, source_count=3, perf_score=0.42)
    spines = client.get("/api/pattern/spines").json()["spines"]
    row = [s for s in spines if s["id"] == sid][0]
    assert row["source_count"] == 3 and row["perf_score"] == 0.42 and row["status"] == "pending"
