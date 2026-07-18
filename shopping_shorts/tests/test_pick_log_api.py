"""픽로그 라우트 — 제작소 결정 지점이 fire-and-forget으로 남긴다(스펙 §7·§8 트랙1)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    return TestClient(app_mod.app)


def test_post_logs_and_persists(client, tmp_path):
    r = client.post("/api/pick_log",
                    json={"stage": "S2", "picked": "초안2",
                          "candidates": ["초안1", "초안2", "초안3"]})
    assert r.status_code == 200 and r.json()["ok"] is True
    from shopping_shorts.store import Store
    rows = Store(tmp_path / "t.db").list_pick_events()
    assert len(rows) == 1
    assert rows[0]["stage"] == "S2" and rows[0]["picked"] == "초안2"
    assert rows[0]["candidates"] == ["초안1", "초안2", "초안3"]


def test_missing_stage_is_422(client):
    r = client.post("/api/pick_log", json={"picked": "x"})
    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_dict_payload_roundtrips_through_route(client, tmp_path):
    client.post("/api/pick_log", json={"stage": "S7", "picked": {"idx": 3},
                                       "rejected": [0, 1, 2, 4]})
    from shopping_shorts.store import Store
    r = Store(tmp_path / "t.db").list_pick_events()[0]
    assert r["picked"] == {"idx": 3} and r["rejected"] == [0, 1, 2, 4]


def test_default_customer_is_zero(client, tmp_path):
    client.post("/api/pick_log", json={"stage": "S3", "picked": "mix"})
    from shopping_shorts.store import Store
    assert Store(tmp_path / "t.db").list_pick_events()[0]["customer_id"] == 0
