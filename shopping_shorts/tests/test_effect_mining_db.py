import sqlite3

import pytest

from shopping_shorts.effect_mining.db import MiningDB


@pytest.fixture
def db(tmp_path):
    return MiningDB(tmp_path / "mining.db")


def test_schedule_due_sources_is_idempotent_while_job_is_active(db):
    source_id = db.add_source("youtube", "keyword", "쇼핑 꿀템", interval_sec=300)

    first = db.schedule_due_sources(now=1_000)
    second = db.schedule_due_sources(now=1_001)

    assert first == [source_id]
    assert second == []
    assert db.queue_counts() == {"queued": 1}


def test_upsert_item_uses_platform_external_id_as_identity(db):
    first_id, first_created = db.upsert_item(
        "youtube", "abc123", "https://youtube.com/shorts/abc123",
        {"title": "처음", "views": 10}, now=1_000,
    )
    second_id, second_created = db.upsert_item(
        "youtube", "abc123", "https://youtube.com/shorts/abc123",
        {"title": "갱신", "views": 25}, now=1_100,
    )

    assert (first_id, first_created) == (second_id, True)
    assert second_created is False
    item = db.get_item(first_id)
    assert item["metadata"]["views"] == 25
    assert item["first_seen_at"] == 1_000
    assert item["last_seen_at"] == 1_100


def test_claim_is_atomic_and_never_returns_same_job_twice(db):
    qid = db.enqueue("acquire", {"item_id": 1}, "acquire:item:1", now=1_000)

    first = db.claim("worker-a", lease_sec=60, now=1_001)
    second = db.claim("worker-b", lease_sec=60, now=1_001)

    assert first["id"] == qid
    assert first["attempts"] == 1
    assert second is None


def test_expired_lease_can_be_recovered_by_another_worker(db):
    qid = db.enqueue("measure", {"item_id": 1}, "measure:item:1:v1", now=1_000)
    assert db.claim("worker-a", lease_sec=10, now=1_001)["id"] == qid

    assert db.recover_expired_leases(now=1_012) == 1
    recovered = db.claim("worker-b", lease_sec=10, now=1_012)

    assert recovered["id"] == qid
    assert recovered["worker_id"] == "worker-b"
    assert recovered["attempts"] == 2


def test_failure_retries_with_exponential_backoff(db):
    qid = db.enqueue("acquire", {"item_id": 1}, "acquire:item:1", max_attempts=4, now=1_000)
    db.claim("worker-a", lease_sec=30, now=1_000)

    state = db.fail(qid, "worker-a", "temporary", now=1_001,
                    base_backoff_sec=10, max_backoff_sec=100)

    assert state == "retry"
    assert db.claim("worker-b", lease_sec=30, now=1_010) is None
    retried = db.claim("worker-b", lease_sec=30, now=1_011)
    assert retried["id"] == qid
    assert retried["attempts"] == 2


def test_failure_moves_job_to_dead_after_max_attempts(db):
    qid = db.enqueue("measure", {"item_id": 1}, "measure:item:1:v1",
                     max_attempts=2, now=1_000)
    db.claim("worker-a", lease_sec=30, now=1_000)
    assert db.fail(qid, "worker-a", "first", now=1_001,
                   base_backoff_sec=1) == "retry"
    db.claim("worker-a", lease_sec=30, now=1_002)

    assert db.fail(qid, "worker-a", "second", now=1_003,
                   base_backoff_sec=1) == "dead"
    assert db.get_job(qid)["state"] == "dead"
    assert db.get_job(qid)["last_error"] == "second"


def test_active_dedupe_key_can_be_enqueued_again_after_completion(db):
    first = db.enqueue("discover", {"source_id": 1}, "discover:source:1", now=1_000)
    assert db.enqueue("discover", {"source_id": 1}, "discover:source:1", now=1_001) == first
    db.claim("worker-a", lease_sec=30, now=1_002)
    db.complete(first, "worker-a", {"found": 3}, now=1_003)

    second = db.enqueue("discover", {"source_id": 1}, "discover:source:1", now=1_004)

    assert second != first
    assert db.queue_counts() == {"done": 1, "queued": 1}


def test_claim_uses_real_sqlite_transaction_across_connections(tmp_path):
    path = tmp_path / "mining.db"
    first_db = MiningDB(path)
    second_db = MiningDB(path)
    first_db.enqueue("acquire", {"item_id": 9}, "acquire:item:9", now=1_000)

    assert first_db.claim("worker-a", lease_sec=30, now=1_001) is not None
    assert second_db.claim("worker-b", lease_sec=30, now=1_001) is None

    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM mining_jobs WHERE state='running'").fetchone()[0] == 1
