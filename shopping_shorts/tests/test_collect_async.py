"""수집 비동기화(2026-07-25): /api/collect가 job_id를 즉시 주고 백그라운드로 수집,
/api/collect/status/{job_id} 폴링으로 결과. census 패턴과 동일."""
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def test_collect_job_store_crud(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.create_collect_job("job1")
    j = s.get_collect_job("job1")
    assert j["status"] == "running" and j["result"] is None
    s.update_collect_job("job1", status="done", result={"count": 3, "items": [1, 2, 3]})
    j = s.get_collect_job("job1")
    assert j["status"] == "done" and j["result"]["count"] == 3
    assert s.get_collect_job("nope") is None


def _client(tmp_path, monkeypatch, items):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setattr(appmod, "collect",
                        lambda platform="instagram", categories=None, limit_channels=None: items)
    return TestClient(appmod.app)


def test_collect_returns_job_then_status_done(tmp_path, monkeypatch):
    items = [{"shortcode": "x", "views": 1}]
    c = _client(tmp_path, monkeypatch, items)
    # POST는 즉시 job_id (동기 아이템 반환 아님)
    r = c.post("/api/collect?platform=youtube").json()
    assert r["ok"] and r["async"] and r["job_id"]
    # TestClient는 BackgroundTask를 응답 뒤 동기 실행 → 이미 done
    s = c.get("/api/collect/status/" + r["job_id"]).json()
    assert s["status"] == "done" and s["count"] == 1 and s["items"] == items


def test_collect_status_error_on_collect_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "b.db"))
    def boom(platform="instagram", categories=None, limit_channels=None):
        raise RuntimeError("apify token=SECRET fail")
    monkeypatch.setattr(appmod, "collect", boom)
    c = TestClient(appmod.app)
    r = c.post("/api/collect?platform=instagram").json()
    s = c.get("/api/collect/status/" + r["job_id"]).json()
    assert s["status"] == "error"
    assert "SECRET" not in s["error"]        # 토큰 마스킹


def test_collect_status_404_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "c.db"))
    c = TestClient(appmod.app)
    assert c.get("/api/collect/status/ghost").status_code == 404
