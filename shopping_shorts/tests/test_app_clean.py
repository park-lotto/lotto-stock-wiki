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


def test_stale_cleaning_reports_failed(tmp_path, monkeypatch):
    # 배포 재시작 등으로 clean BackgroundTask가 죽으면 clean_status='cleaning'이 DB에 영원히
    # 남아 프론트가 무한 "복원하는 중"에 갇힌다. status GET이 staleness를 보고 failed로 알려
    # 재시도 UI를 열어야 한다(2026-07-23 실사고).
    c = _client(tmp_path, monkeypatch)
    _job_with_plan(c, monkeypatch)
    appmod.Store(appmod.DB_PATH).update_mix_job("j", clean_status="cleaning", clean_error=None)
    monkeypatch.setattr(appmod, "_render_is_stale", lambda job: True)   # 죽은 태스크 모사
    d = c.get("/api/mix/status/j").json()
    assert d["clean_status"] == "failed"
    assert d["clean_error"]
    # DB는 GET이 안 건드린다(응답에서만 알림)
    assert appmod.Store(appmod.DB_PATH).get_mix_job("j")["clean_status"] == "cleaning"


def test_fresh_cleaning_stays_cleaning(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job_with_plan(c, monkeypatch)
    appmod.Store(appmod.DB_PATH).update_mix_job("j", clean_status="cleaning", clean_error=None)
    monkeypatch.setattr(appmod, "_render_is_stale", lambda job: False)  # 아직 진행 중(신선)
    d = c.get("/api/mix/status/j").json()
    assert d["clean_status"] == "cleaning"


def test_stale_preview_reports_failed(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job_with_plan(c, monkeypatch)
    appmod.Store(appmod.DB_PATH).update_mix_job("j", preview_status="rendering")
    monkeypatch.setattr(appmod, "_render_is_stale", lambda job: True)
    d = c.get("/api/mix/status/j").json()
    assert d["preview_status"] == "failed"


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
