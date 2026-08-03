from fastapi.testclient import TestClient
import shopping_shorts.app as appmod
from shopping_shorts.app import app

client = TestClient(app)


def test_overseas_feed_empty_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    r = client.get("/api/overseas/feed")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["items"] == []


def test_overseas_status_shape():
    r = client.get("/api/overseas/status")
    assert r.status_code == 200
    assert "status" in r.json()
