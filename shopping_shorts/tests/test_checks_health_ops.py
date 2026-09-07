import json
import sqlite3
from datetime import datetime, timedelta, timezone
from shopping_shorts.checks.health import h_collect_zero, h_stuck_jobs, h_dead_key_recall


def _db(tmp_path):
    p = tmp_path / "reference.db"
    c = sqlite3.connect(p)
    c.executescript("""
    CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE job_queue(id INTEGER PRIMARY KEY, task TEXT, state TEXT, heartbeat_at TEXT, claimed_at TEXT);
    CREATE TABLE mix_jobs(job_id TEXT, status TEXT, preview_status TEXT, clean_status TEXT, fx_status TEXT, updated_at TEXT);
    CREATE TABLE api_events(id INTEGER PRIMARY KEY, ts TEXT, day TEXT, service TEXT, outcome TEXT, key_tail TEXT, customer_id TEXT);
    """)
    c.commit()
    return p, c


def test_collect_zero_flags_platform_with_items_zero(tmp_path):
    p, c = _db(tmp_path)
    c.execute("INSERT INTO settings VALUES(?,?)", ("last_run::threads",
              json.dumps({"items": [], "collected_at": datetime.now(timezone.utc).isoformat()})))
    c.commit()
    by = {s.item: s for s in h_collect_zero.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})}
    assert by["h_collect_zero::threads"].ok is False and by["h_collect_zero::threads"].value == 0


def test_stuck_running_over_5min_is_red_and_fx_included(tmp_path):
    p, c = _db(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(minutes=9)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO job_queue(task,state,heartbeat_at,claimed_at) VALUES('render','running',?,?)", (old, old))
    c.execute("INSERT INTO mix_jobs VALUES('j1','done',NULL,NULL,'queued',?)",
              ((datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat(),))
    c.commit()
    by = {s.item: s for s in h_stuck_jobs.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})}
    assert by["h_stuck_jobs::worker_silent"].ok is False and by["h_stuck_jobs::worker_silent"].value == 1
    assert by["h_stuck_jobs::fx"].ok is False


def test_dead_key_recalled_after_auth_dead_is_red(tmp_path):
    p, c = _db(tmp_path)
    t0 = datetime.now(timezone.utc)
    c.execute("INSERT INTO api_events(ts,day,service,outcome,key_tail) VALUES(?,?,?,?,?)",
              ((t0 - timedelta(hours=3)).isoformat(), "d", "gemini", "auth_dead", "abc123"))
    c.execute("INSERT INTO api_events(ts,day,service,outcome,key_tail) VALUES(?,?,?,?,?)",
              ((t0 - timedelta(hours=1)).isoformat(), "d", "gemini", "auth_dead", "abc123"))
    c.commit()
    s = h_dead_key_recall.measure({"live_db": p, "base_url": None, "now": t0})[0]
    assert s.ok is False and s.value == 1 and "abc123" in s.detail
