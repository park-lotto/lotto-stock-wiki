from fastapi.testclient import TestClient
from shopping_shorts import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(appmod.app)


def _job_with_plan(c, monkeypatch):
    appmod.Store(appmod.DB_PATH).create_mix_job("j", ["u"], 30, "template")
    appmod.Store(appmod.DB_PATH).update_mix_job("j", edit_plan={"beats": [{"beat_idx": 0}]})


def test_clean_schedules_and_marks_cleaning(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job_with_plan(c, monkeypatch)
    monkeypatch.setattr(appmod, "run_clean_sources", lambda *a, **k: None)
    r = c.post("/api/produce/mix/clean", json={"job_id": "j"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert appmod.Store(appmod.DB_PATH).get_mix_job("j")["clean_status"] == "cleaning"


def test_clean_requires_plan(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/produce/mix/clean", json={"job_id": "nope"})
    assert r.status_code == 422


def test_status_exposes_clean_fields(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job_with_plan(c, monkeypatch)
    appmod.Store(appmod.DB_PATH).update_mix_job("j", clean_status="ready", clean_error=None)
    d = c.get("/api/mix/status/j").json()
    assert d["clean_status"] == "ready"
    assert "clean_error" in d
