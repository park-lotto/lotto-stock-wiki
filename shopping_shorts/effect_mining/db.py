"""SQLite persistence for the effect-mining scheduler and workers."""

from __future__ import annotations

import json
import hashlib
import sqlite3
import time
from pathlib import Path


ACTIVE_STATES = ("queued", "retry", "running")


class MiningDB:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        return con

    def _init_schema(self):
        with self._connect() as con:
            con.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS mining_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    query TEXT NOT NULL,
                    interval_sec INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    next_run_at INTEGER NOT NULL DEFAULT 0,
                    last_scheduled_at INTEGER,
                    created_at INTEGER NOT NULL,
                    UNIQUE(platform, source_kind, query)
                );
                CREATE TABLE IF NOT EXISTS mining_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    media_path TEXT,
                    media_sha256 TEXT,
                    first_seen_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    UNIQUE(platform, external_id)
                );
                CREATE TABLE IF NOT EXISTS mining_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 5,
                    available_at INTEGER NOT NULL,
                    worker_id TEXT,
                    lease_until INTEGER,
                    heartbeat_at INTEGER,
                    last_error TEXT,
                    result_json TEXT,
                    created_at INTEGER NOT NULL,
                    started_at INTEGER,
                    finished_at INTEGER
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_mining_jobs_active_dedupe
                    ON mining_jobs(dedupe_key)
                    WHERE state IN ('queued', 'retry', 'running');
                CREATE INDEX IF NOT EXISTS idx_mining_jobs_claim
                    ON mining_jobs(state, available_at, priority, id);
                CREATE TABLE IF NOT EXISTS mining_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL REFERENCES mining_items(id),
                    analyzer TEXT NOT NULL,
                    analyzer_version TEXT NOT NULL,
                    signal_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    UNIQUE(item_id, analyzer, analyzer_version)
                );
                CREATE TABLE IF NOT EXISTS effect_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL REFERENCES mining_items(id),
                    signal_id INTEGER NOT NULL REFERENCES mining_signals(id),
                    candidate_kind TEXT NOT NULL,
                    start_sec REAL NOT NULL,
                    end_sec REAL NOT NULL,
                    score REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'candidate',
                    created_at INTEGER NOT NULL,
                    UNIQUE(signal_id, candidate_kind, start_sec, end_sec)
                );
                CREATE TABLE IF NOT EXISTS mining_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL REFERENCES mining_sources(id),
                    started_at INTEGER NOT NULL,
                    finished_at INTEGER,
                    found_count INTEGER NOT NULL DEFAULT 0,
                    new_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                """
            )

    @staticmethod
    def _now(now=None):
        return int(time.time() if now is None else now)

    @staticmethod
    def _json(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    def add_source(self, platform, source_kind, query, interval_sec, enabled=True, now=None):
        if not platform or not source_kind or not query:
            raise ValueError("platform, source_kind and query are required")
        if int(interval_sec) <= 0:
            raise ValueError("interval_sec must be positive")
        stamp = self._now(now)
        with self._connect() as con:
            con.execute(
                "INSERT INTO mining_sources(platform,source_kind,query,interval_sec,enabled,created_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(platform,source_kind,query) DO UPDATE SET "
                "interval_sec=excluded.interval_sec, enabled=excluded.enabled",
                (platform, source_kind, query, int(interval_sec), int(bool(enabled)), stamp),
            )
            row = con.execute(
                "SELECT id FROM mining_sources WHERE platform=? AND source_kind=? AND query=?",
                (platform, source_kind, query),
            ).fetchone()
        return int(row["id"])

    def list_sources(self):
        with self._connect() as con:
            rows = con.execute("SELECT * FROM mining_sources ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def get_source(self, source_id):
        with self._connect() as con:
            row = con.execute("SELECT * FROM mining_sources WHERE id=?", (source_id,)).fetchone()
        return dict(row) if row else None

    def schedule_due_sources(self, now=None):
        stamp = self._now(now)
        scheduled = []
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute(
                "SELECT * FROM mining_sources WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at,id",
                (stamp,),
            ).fetchall()
            for row in rows:
                key = f"discover:source:{row['id']}"
                active = con.execute(
                    "SELECT id FROM mining_jobs WHERE dedupe_key=? "
                    "AND state IN ('queued','retry','running')",
                    (key,),
                ).fetchone()
                if active:
                    continue
                con.execute(
                    "INSERT INTO mining_jobs(task,payload_json,dedupe_key,state,available_at,created_at) "
                    "VALUES('discover',?,?, 'queued',?,?)",
                    (self._json({"source_id": row["id"]}), key, stamp, stamp),
                )
                con.execute(
                    "UPDATE mining_sources SET last_scheduled_at=?,next_run_at=? WHERE id=?",
                    (stamp, stamp + int(row["interval_sec"]), row["id"]),
                )
                scheduled.append(int(row["id"]))
        return scheduled

    def upsert_item(self, platform, external_id, url, metadata, now=None):
        stamp = self._now(now)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute(
                "SELECT id FROM mining_items WHERE platform=? AND external_id=?",
                (platform, external_id),
            ).fetchone()
            if existing:
                con.execute(
                    "UPDATE mining_items SET url=?,metadata_json=?,last_seen_at=? WHERE id=?",
                    (url, self._json(metadata or {}), stamp, existing["id"]),
                )
                return int(existing["id"]), False
            cur = con.execute(
                "INSERT INTO mining_items(platform,external_id,url,metadata_json,first_seen_at,last_seen_at) "
                "VALUES(?,?,?,?,?,?)",
                (platform, external_id, url, self._json(metadata or {}), stamp, stamp),
            )
            return int(cur.lastrowid), True

    def get_item(self, item_id):
        with self._connect() as con:
            row = con.execute("SELECT * FROM mining_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["metadata"] = json.loads(out.pop("metadata_json"))
        return out

    def list_items(self):
        with self._connect() as con:
            rows = con.execute("SELECT * FROM mining_items ORDER BY id").fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            out.append(item)
        return out

    def set_item_media(self, item_id, media_path, now=None):
        path = Path(media_path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with self._connect() as con:
            con.execute(
                "UPDATE mining_items SET media_path=?,media_sha256=?,last_seen_at=? WHERE id=?",
                (str(path), digest, self._now(now), item_id),
            )
        return digest

    def save_signal(self, item_id, analyzer, analyzer_version, signal, now=None):
        with self._connect() as con:
            con.execute(
                "INSERT INTO mining_signals(item_id,analyzer,analyzer_version,signal_json,created_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(item_id,analyzer,analyzer_version) DO NOTHING",
                (item_id, analyzer, analyzer_version, self._json(signal), self._now(now)),
            )
            row = con.execute(
                "SELECT id FROM mining_signals WHERE item_id=? AND analyzer=? AND analyzer_version=?",
                (item_id, analyzer, analyzer_version),
            ).fetchone()
        return int(row["id"])

    def get_signal(self, signal_id):
        with self._connect() as con:
            row = con.execute("SELECT * FROM mining_signals WHERE id=?", (signal_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["signal"] = json.loads(out.pop("signal_json"))
        return out

    def find_signal(self, item_id, analyzer, analyzer_version):
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM mining_signals WHERE item_id=? AND analyzer=? AND analyzer_version=?",
                (item_id, analyzer, analyzer_version),
            ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["signal"] = json.loads(out.pop("signal_json"))
        return out

    def list_signals(self, item_id=None):
        sql, params = "SELECT * FROM mining_signals", []
        if item_id is not None:
            sql += " WHERE item_id=?"
            params.append(item_id)
        sql += " ORDER BY id"
        with self._connect() as con:
            rows = con.execute(sql, params).fetchall()
        return [self.get_signal(row["id"]) for row in rows]

    def add_candidate(self, item_id, signal_id, candidate, now=None):
        with self._connect() as con:
            con.execute(
                "INSERT INTO effect_candidates(item_id,signal_id,candidate_kind,start_sec,end_sec,"
                "score,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(signal_id,candidate_kind,start_sec,end_sec) DO NOTHING",
                (item_id, signal_id, candidate["kind"], float(candidate["start_sec"]),
                 float(candidate["end_sec"]), float(candidate["score"]),
                 self._json(candidate.get("evidence") or {}), self._now(now)),
            )

    def list_candidates(self, item_id=None):
        sql, params = "SELECT * FROM effect_candidates", []
        if item_id is not None:
            sql += " WHERE item_id=?"
            params.append(item_id)
        sql += " ORDER BY id"
        with self._connect() as con:
            rows = con.execute(sql, params).fetchall()
        out = []
        for row in rows:
            candidate = dict(row)
            candidate["evidence"] = json.loads(candidate.pop("evidence_json"))
            out.append(candidate)
        return out

    def start_run(self, source_id, now=None):
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO mining_runs(source_id,started_at) VALUES(?,?)",
                (source_id, self._now(now)),
            )
        return int(cur.lastrowid)

    def finish_run(self, run_id, found_count, new_count, error=None, now=None):
        with self._connect() as con:
            con.execute(
                "UPDATE mining_runs SET finished_at=?,found_count=?,new_count=?,error=? WHERE id=?",
                (self._now(now), int(found_count), int(new_count), error, run_id),
            )

    def get_run(self, source_id):
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM mining_runs WHERE source_id=? ORDER BY id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
        return dict(row) if row else None

    def enqueue(self, task, payload, dedupe_key, priority=0, max_attempts=5,
                available_at=None, now=None):
        stamp = self._now(now)
        due = stamp if available_at is None else int(available_at)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            active = con.execute(
                "SELECT id FROM mining_jobs WHERE dedupe_key=? "
                "AND state IN ('queued','retry','running')",
                (dedupe_key,),
            ).fetchone()
            if active:
                return int(active["id"])
            cur = con.execute(
                "INSERT INTO mining_jobs(task,payload_json,dedupe_key,state,priority,max_attempts,"
                "available_at,created_at) VALUES(?,?,?,'queued',?,?,?,?)",
                (task, self._json(payload), dedupe_key, int(priority), int(max_attempts), due, stamp),
            )
            return int(cur.lastrowid)

    def claim(self, worker_id, lease_sec=120, tasks=None, now=None):
        stamp = self._now(now)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            params = [stamp]
            task_sql = ""
            if tasks:
                marks = ",".join("?" for _ in tasks)
                task_sql = f" AND task IN ({marks})"
                params.extend(tasks)
            row = con.execute(
                "SELECT id FROM mining_jobs WHERE state IN ('queued','retry') AND available_at<=?"
                + task_sql + " ORDER BY priority DESC,available_at,id LIMIT 1",
                params,
            ).fetchone()
            if not row:
                return None
            con.execute(
                "UPDATE mining_jobs SET state='running',worker_id=?,lease_until=?,heartbeat_at=?,"
                "attempts=attempts+1,started_at=COALESCE(started_at,?) WHERE id=?",
                (worker_id, stamp + int(lease_sec), stamp, stamp, row["id"]),
            )
            claimed = con.execute("SELECT * FROM mining_jobs WHERE id=?", (row["id"],)).fetchone()
        return self._job_dict(claimed)

    def heartbeat(self, job_id, worker_id, lease_sec=120, now=None):
        stamp = self._now(now)
        with self._connect() as con:
            cur = con.execute(
                "UPDATE mining_jobs SET heartbeat_at=?,lease_until=? "
                "WHERE id=? AND state='running' AND worker_id=?",
                (stamp, stamp + int(lease_sec), job_id, worker_id),
            )
        return cur.rowcount == 1

    def recover_expired_leases(self, now=None):
        stamp = self._now(now)
        with self._connect() as con:
            cur = con.execute(
                "UPDATE mining_jobs SET state='queued',worker_id=NULL,lease_until=NULL,heartbeat_at=NULL,"
                "available_at=? WHERE state='running' AND lease_until<?",
                (stamp, stamp),
            )
        return int(cur.rowcount)

    def complete(self, job_id, worker_id, result=None, now=None):
        stamp = self._now(now)
        with self._connect() as con:
            cur = con.execute(
                "UPDATE mining_jobs SET state='done',result_json=?,finished_at=?,worker_id=NULL,"
                "lease_until=NULL WHERE id=? AND state='running' AND worker_id=?",
                (self._json(result or {}), stamp, job_id, worker_id),
            )
        if cur.rowcount != 1:
            raise RuntimeError("job lease is not owned by this worker")

    def fail(self, job_id, worker_id, error, now=None, base_backoff_sec=30,
             max_backoff_sec=3600):
        stamp = self._now(now)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT attempts,max_attempts FROM mining_jobs "
                "WHERE id=? AND state='running' AND worker_id=?",
                (job_id, worker_id),
            ).fetchone()
            if not row:
                raise RuntimeError("job lease is not owned by this worker")
            if int(row["attempts"]) >= int(row["max_attempts"]):
                state, available = "dead", stamp
            else:
                state = "retry"
                delay = min(int(base_backoff_sec) * (2 ** (int(row["attempts"]) - 1)),
                            int(max_backoff_sec))
                available = stamp + delay
            con.execute(
                "UPDATE mining_jobs SET state=?,available_at=?,last_error=?,worker_id=NULL,"
                "lease_until=NULL,heartbeat_at=NULL,finished_at=? WHERE id=?",
                (state, available, str(error), stamp if state == "dead" else None, job_id),
            )
        return state

    def get_job(self, job_id):
        with self._connect() as con:
            row = con.execute("SELECT * FROM mining_jobs WHERE id=?", (job_id,)).fetchone()
        return self._job_dict(row) if row else None

    def queue_counts(self):
        with self._connect() as con:
            rows = con.execute(
                "SELECT state,COUNT(*) AS n FROM mining_jobs GROUP BY state ORDER BY state"
            ).fetchall()
        return {row["state"]: int(row["n"]) for row in rows}

    def status_summary(self):
        with self._connect() as con:
            totals = {}
            for name, table in (("items", "mining_items"), ("signals", "mining_signals"),
                                ("candidates", "effect_candidates")):
                totals[name] = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return {"queue": self.queue_counts(), "sources": self.list_sources(), "totals": totals}

    @staticmethod
    def _job_dict(row):
        out = dict(row)
        out["payload"] = json.loads(out.pop("payload_json"))
        raw = out.pop("result_json")
        out["result"] = json.loads(raw) if raw else None
        return out
