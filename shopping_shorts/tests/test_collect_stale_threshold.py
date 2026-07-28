"""수집 job stale 판정 임계값 — apify/playwright 경로마다 달라야 한다.

★2026-07-28 회귀: _COLLECT_STALE_MIN을 60→15로 낮췄더니 apify 경로(on_progress
콜백이 없어 done까지 updated_at이 한 번도 안 갱신됨. 실측 소요 28분)가 15분 시점에
"중단됨"으로 잘못 판정됐다. playwright 경로는 채널마다 진행률을 써 updated_at이
갱신되므로 15분로 짧게 둬도 된다. 이 둘을 다시 하나로 합치면 이 회귀가 재발한다.
"""
from datetime import datetime, timedelta, timezone

from shopping_shorts import app as app_module
from shopping_shorts import config
from shopping_shorts.store import Store


def _make_stale_running_job(tmp_path, minutes_old):
    db = tmp_path / "t.db"
    store = Store(db)
    store.create_collect_job("J1")
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_old)).isoformat()
    with store._conn() as c:
        c.execute("UPDATE collect_jobs SET updated_at=? WHERE job_id=?", (old_ts, "J1"))
    return db


def test_apify_20min_old_running_job_is_not_stale(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "INSTAGRAM_SCRAPER", "apify")
    db = _make_stale_running_job(tmp_path, 20)
    monkeypatch.setattr(app_module, "DB_PATH", db)

    result = app_module.api_collect_status("J1")

    assert result["status"] == "running", "apify는 60분 임계값이라 20분은 stale이 아니어야 한다"


def test_playwright_20min_old_running_job_is_stale(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "INSTAGRAM_SCRAPER", "playwright")
    db = _make_stale_running_job(tmp_path, 20)
    monkeypatch.setattr(app_module, "DB_PATH", db)

    result = app_module.api_collect_status("J1")

    assert result["status"] == "error", "playwright는 15분 임계값이라 20분은 stale로 잡혀야 한다"
