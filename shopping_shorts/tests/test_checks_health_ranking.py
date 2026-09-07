import json
import sqlite3
from datetime import datetime, timedelta, timezone
from shopping_shorts.checks import discover, db, run_checks
from shopping_shorts.checks.health import h_ranking_fresh
from shopping_shorts.checks.verdict import GRAY


def _live(tmp_path, collected_at):
    p = tmp_path / "reference.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE last_run(id INTEGER PRIMARY KEY, items_json TEXT, collected_at TEXT)")
    c.execute("INSERT INTO settings VALUES(?,?)", ("last_run::youtube",
              json.dumps({"items": [{"a": 1}], "collected_at": collected_at})))
    c.execute("INSERT INTO last_run VALUES(1, ?, ?)", (json.dumps([{"a": 1}]), collected_at))
    c.commit()
    return p


def test_fresh_within_26h_is_ok(tmp_path):
    now = datetime.now(timezone.utc)
    p = _live(tmp_path, (now - timedelta(hours=2)).isoformat())
    out = h_ranking_fresh.measure({"live_db": p, "base_url": None, "now": now})
    by = {s.item: s for s in out}
    assert by["h_ranking_fresh::youtube"].ok is True
    assert by["h_ranking_fresh::instagram"].ok is True


def test_stale_over_26h_is_red_and_missing_platform_is_red(tmp_path):
    now = datetime.now(timezone.utc)
    p = _live(tmp_path, (now - timedelta(hours=30)).isoformat())
    by = {s.item: s for s in h_ranking_fresh.measure({"live_db": p, "base_url": None, "now": now})}
    assert by["h_ranking_fresh::youtube"].ok is False
    assert by["h_ranking_fresh::tiktok"].ok is False and "없음" in by["h_ranking_fresh::tiktok"].detail


def test_unreadable_db_is_gray(tmp_path):
    out = h_ranking_fresh.measure({"live_db": tmp_path / "nope.db", "base_url": None,
                                   "now": datetime.now(timezone.utc)})
    assert all(s.ok is None for s in out)


def test_run_checks_records_gray_for_broken_module(tmp_path, monkeypatch):
    """discover()의 LAST_ERRORS를 러너가 GRAY Result로 기록하는지 — discover.py의
    docstring 계약("러너(Task 4)는 discover() 호출 뒤 LAST_ERRORS를 읽어 GRAY 결과로
    기록해야 한다")을 검증한다. 정상 항목은 그대로 기록되고, 깨진 모듈은 checks.db에
    GRAY Result가 남아야 한다."""
    import types

    good_calls = []

    def good_measure(ctx):
        good_calls.append(ctx)
        return []

    good_mod = types.SimpleNamespace(
        __name__="shopping_shorts.checks.health.h_good_dummy",
        META={"name": "정상 더미", "every": "1h"},
        measure=good_measure,
    )

    def fake_discover(kind):
        discover.LAST_ERRORS.clear()
        discover.LAST_ERRORS.append(
            ("shopping_shorts.checks.health.h_broken_dummy", "ValueError('일부러 깨진 모듈')")
        )
        return [good_mod]

    monkeypatch.setattr(run_checks.discover, "discover", fake_discover)

    conn = db.open_db(tmp_path / "checks.db")
    run_id = db.start_run(conn, run_checks.SERVICE, "health", "deadbeef")
    ctx = {"live_db": tmp_path / "nope.db", "base_url": None, "now": datetime.now(timezone.utc)}
    run_checks.run_health(conn, ctx, run_id=run_id, force=True)

    rows = db.latest_results(conn, run_id)
    assert len(good_calls) == 1, "정상 항목은 그대로 measure가 호출돼야 한다"
    gray_rows = [r for r in rows if r["verdict"] == GRAY]
    assert len(gray_rows) == 1
    assert "h_broken_dummy" in gray_rows[0]["signature"]
    assert "ValueError" in gray_rows[0]["reason"]
