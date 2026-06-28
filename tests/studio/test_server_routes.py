from fastapi.testclient import TestClient
import dashboard.server as srv


def test_gallery_empty_returns_list(monkeypatch, tmp_path):
    monkeypatch.setattr(srv, "STUDIO_DIR", str(tmp_path))
    client = TestClient(srv.app)
    r = client.get("/studio/gallery")
    assert r.status_code == 200
    assert r.json() == []


def test_generate_streams_events(monkeypatch):
    def fake_gen(date):
        yield {"type": "step", "id": 1, "status": "done", "message": "x"}
        yield {"type": "done", "png": "a.png", "html": "a.html", "thumb": "a.png", "sent_tg": True}
    monkeypatch.setattr(srv, "generate_briefing", fake_gen)
    client = TestClient(srv.app)
    with client.stream("POST", "/studio/generate?date=2026-06-28") as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert "data:" in body
    assert '"type": "done"' in body or '"type":"done"' in body
