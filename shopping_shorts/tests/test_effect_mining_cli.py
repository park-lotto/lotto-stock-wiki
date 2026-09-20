import io
import json

import pytest

from shopping_shorts.effect_mining.cli import main
from shopping_shorts.effect_mining.db import MiningDB
from shopping_shorts.effect_mining.runner import scheduler_tick, worker_tick


class RecordingPipeline:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def execute(self, task, payload, now=None):
        self.calls.append((task, payload))
        if self.fail:
            raise RuntimeError("temporary connector failure")
        return {"accepted": payload["value"]}


def test_scheduler_tick_recovers_leases_and_schedules_due_sources(tmp_path):
    db = MiningDB(tmp_path / "mining.db")
    source_id = db.add_source("youtube", "keyword", "살림템", 300, now=1_000)
    dead_job = db.enqueue("acquire", {"item_id": 9}, "acquire:item:9", now=900)
    db.claim("old-worker", lease_sec=10, now=900)

    result = scheduler_tick(db, now=1_000)

    assert result == {"recovered": 1, "scheduled_sources": [source_id]}
    assert db.get_job(dead_job)["state"] == "queued"


def test_worker_tick_completes_one_job(tmp_path):
    db = MiningDB(tmp_path / "mining.db")
    qid = db.enqueue("demo", {"value": 7}, "demo:7", now=1_000)
    pipeline = RecordingPipeline()

    result = worker_tick(db, pipeline, "worker-a", now=1_000)

    assert result == {"job_id": qid, "task": "demo", "state": "done"}
    assert pipeline.calls == [("demo", {"value": 7})]
    assert db.get_job(qid)["result"] == {"accepted": 7}


def test_worker_tick_records_retry_instead_of_crashing_loop(tmp_path):
    db = MiningDB(tmp_path / "mining.db")
    qid = db.enqueue("demo", {"value": 7}, "demo:7", now=1_000)

    result = worker_tick(db, RecordingPipeline(fail=True), "worker-a", now=1_000,
                         base_backoff_sec=5)

    assert result == {"job_id": qid, "task": "demo", "state": "retry"}
    assert "temporary connector failure" in db.get_job(qid)["last_error"]


def test_cli_init_add_source_schedule_and_status(tmp_path):
    db_path = tmp_path / "mining.db"
    out = io.StringIO()
    assert main(["--db", str(db_path), "init"], stdout=out) == 0
    assert json.loads(out.getvalue())["ok"] is True

    out = io.StringIO()
    assert main([
        "--db", str(db_path), "add-source", "youtube", "keyword", "쇼핑 꿀템",
        "--interval-sec", "600",
    ], stdout=out) == 0
    source_id = json.loads(out.getvalue())["source_id"]

    out = io.StringIO()
    assert main(["--db", str(db_path), "schedule", "--once"], stdout=out) == 0
    assert json.loads(out.getvalue())["scheduled_sources"] == [source_id]

    out = io.StringIO()
    assert main(["--db", str(db_path), "status"], stdout=out) == 0
    status = json.loads(out.getvalue())
    assert status["queue"] == {"queued": 1}
    assert status["sources"][0]["query"] == "쇼핑 꿀템"
    assert status["totals"] == {"items": 0, "signals": 0, "candidates": 0}


def test_cli_rejects_non_positive_interval(tmp_path):
    with pytest.raises(SystemExit):
        main([
            "--db", str(tmp_path / "mining.db"), "add-source",
            "youtube", "keyword", "x", "--interval-sec", "0",
        ], stdout=io.StringIO())
