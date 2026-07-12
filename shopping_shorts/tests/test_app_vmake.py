from fastapi.testclient import TestClient
from shopping_shorts import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(appmod.app)


def test_set_and_get_vmake_key(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/settings/vmake_key", json={"key": "appkey:secret"})
    assert r.status_code == 200 and r.json()["ok"] is True
    g = c.get("/api/settings/vmake_key")
    assert g.json()["configured"] is True
    assert "secret" not in str(g.json())              # 원문 미노출


def test_get_vmake_key_unset(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/settings/vmake_key").json()["configured"] is False


def test_mix_start_passes_subtitle_removal(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    captured = {}
    orig_create = appmod.Store.create_mix_job
    def spy(self, job_id, urls, target_seconds, structure, subtitle_removal=False):
        captured["sr"] = subtitle_removal
    monkeypatch.setattr(appmod.Store, "create_mix_job", spy)
    monkeypatch.setattr(appmod, "run_mix_job", lambda *a, **k: None)
    r = c.post("/api/mix/start", json={"urls": ["u1", "u2"], "target_seconds": 30,
                                       "structure": "template", "subtitle_removal": True})
    assert r.status_code == 200
    assert captured["sr"] is True
