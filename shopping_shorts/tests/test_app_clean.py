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


def test_clean_thumb_clean_404_before_ready(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job_with_plan(c, monkeypatch)                    # clean_status 미설정
    r = c.get("/api/produce/mix/clean_thumb/j?kind=clean")
    assert r.status_code == 404


def test_clean_thumb_original_serves(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job_with_plan(c, monkeypatch)
    monkeypatch.setattr(appmod, "_resolve_sources", lambda job, work: {"s0": "/orig/s0.mp4"})
    monkeypatch.setattr(appmod.frame_extract, "_probe_duration", lambda p: 4.0)
    img = tmp_path / "original.jpg"; img.write_bytes(b"\xff\xd8jpg")
    monkeypatch.setattr(appmod.frame_extract, "extract_frame_at",
                        lambda src, d, ts, filename="f.jpg": img)
    r = c.get("/api/produce/mix/clean_thumb/j?kind=original")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
