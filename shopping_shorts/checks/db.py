"""checks.db — 점검 결과 전용 SQLite. 라이브 reference.db에는 절대 쓰지 않는다(설계 D8)."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shopping_shorts.checks.verdict import Result, Sample

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "checks.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS check_runs(
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  service TEXT NOT NULL, trigger TEXT NOT NULL, head_sha TEXT,
  started TEXT NOT NULL, finished TEXT, verdict TEXT, l0_json TEXT);
CREATE TABLE IF NOT EXISTS check_results(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL, layer TEXT NOT NULL, name TEXT NOT NULL,
  verdict TEXT NOT NULL, reason TEXT, signature TEXT, page TEXT,
  evidence_dir TEXT, dur_ms INTEGER, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_results_sig ON check_results(signature, run_id);
CREATE TABLE IF NOT EXISTS health_samples(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item TEXT NOT NULL, name TEXT NOT NULL, ts TEXT NOT NULL,
  value REAL, ok INTEGER, detail TEXT, evidence_url TEXT);
CREATE INDEX IF NOT EXISTS ix_samples_item ON health_samples(item, ts);
CREATE TABLE IF NOT EXISTS pytest_baseline(
  day TEXT PRIMARY KEY, head_sha TEXT, failed_ids_json TEXT, n_passed INTEGER, n_failed INTEGER);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_db(path=None):
    p = Path(path or DEFAULT_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def start_run(conn, service, trigger, head_sha):
    cur = conn.execute("INSERT INTO check_runs(service,trigger,head_sha,started) VALUES(?,?,?,?)",
                       (service, trigger, head_sha, _now()))
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id, verdict, l0_json=""):
    conn.execute("UPDATE check_runs SET finished=?, verdict=?, l0_json=? WHERE run_id=?",
                 (_now(), verdict, l0_json, run_id))
    conn.commit()


def add_result(conn, run_id, r: Result):
    conn.execute("INSERT INTO check_results(run_id,layer,name,verdict,reason,signature,page,"
                 "evidence_dir,dur_ms,ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (run_id, r.layer, r.name, r.verdict, r.reason, r.signature, r.page,
                  r.evidence_dir, r.dur_ms, _now()))
    conn.commit()


def add_sample(conn, s: Sample, ts=None):
    conn.execute("INSERT INTO health_samples(item,name,ts,value,ok,detail,evidence_url) "
                 "VALUES(?,?,?,?,?,?,?)",
                 (s.item, s.name, ts or _now(), s.value,
                  None if s.ok is None else int(s.ok), s.detail, s.evidence_url))
    conn.commit()


def previous_verdict(conn, signature, before_run_id):
    row = conn.execute("SELECT verdict FROM check_results WHERE signature=? AND run_id<? "
                       "ORDER BY run_id DESC LIMIT 1", (signature, before_run_id)).fetchone()
    return row["verdict"] if row else None


def latest_results(conn, run_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM check_results WHERE run_id=? ORDER BY id", (run_id,))]


def last_sample_ts(conn, item):
    row = conn.execute("SELECT ts FROM health_samples WHERE item=? ORDER BY ts DESC LIMIT 1",
                       (item,)).fetchone()
    return row["ts"] if row else None


def save_pytest_baseline(conn, day, head_sha, failed_ids, n_passed):
    conn.execute("INSERT OR REPLACE INTO pytest_baseline VALUES(?,?,?,?,?)",
                 (day, head_sha, json.dumps(sorted(failed_ids)), n_passed, len(failed_ids)))
    conn.commit()
