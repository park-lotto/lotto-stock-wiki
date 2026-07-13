from fastapi.testclient import TestClient
from shopping_shorts import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(appmod.app)


def test_seed_endpoints(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/seeds", json={"platform": "youtube", "kind": "keyword", "value": "살림꿀팁"}).json()["ok"]
    g = c.get("/api/seeds?platform=youtube").json()
    assert g["items"][0]["value"] == "살림꿀팁"
    c.request("DELETE", "/api/seeds", json={"platform": "youtube", "value": "살림꿀팁"})
    assert c.get("/api/seeds?platform=youtube").json()["items"] == []


def test_reference_platform(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/reference?platform=youtube").json()
    assert r["ok"] and r["items"] == []
