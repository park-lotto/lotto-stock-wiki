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
    def spy(self, job_id, urls, target_seconds, structure, subtitle_removal=False, **kw):
        captured["sr"] = subtitle_removal
        captured["cid"] = kw.get("customer_id")   # 유료게이트: 렌더 크레딧 귀속 cid도 전달됨
    monkeypatch.setattr(appmod.Store, "create_mix_job", spy)
    monkeypatch.setattr(appmod, "run_mix_job", lambda *a, **k: None)
    r = c.post("/api/mix/start", json={"urls": ["https://www.instagram.com/reel/AAA111/",
                                       "https://www.instagram.com/reel/BBB222/"],
                                       "target_seconds": 30,
                                       "structure": "template", "subtitle_removal": True})
    assert r.status_code == 200
    assert captured["sr"] is True
