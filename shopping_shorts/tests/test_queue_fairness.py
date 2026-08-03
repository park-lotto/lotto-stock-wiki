"""큐 공평 분배·우선순위·WAL — "누가 쓰면 느려지는" 구조를 없앤 것(2026-07-30).

배경: 워커 1개 + 순수 FIFO였다. 한 고객이 5건을 밀어넣으면 뒤에 온 고객이 그게 다
끝날 때까지 굶었고, 예열 같은 배경작업이 남의 렌더를 앞질렀다.
"""
import sqlite3

import pytest

from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_wal_is_enabled(store):
    """워커를 여러 개 띄우기 위한 선행조건 — WAL이 아니면 database is locked가 터진다."""
    with store._conn() as c:
        assert c.execute("pragma journal_mode").fetchone()[0].lower() == "wal"


def test_customer_gets_only_one_job_running_at_a_time(store):
    store.enqueue("render", {"customer_id": "7"})
    store.enqueue("render", {"customer_id": "7"})       # 같은 고객의 2번째
    store.enqueue("render", {"customer_id": "9"})       # 다른 고객

    first = store.claim_next()
    second = store.claim_next()
    assert first and second
    # 7번의 2건이 연달아 잡히면 9번이 굶는다 → 두 번째는 반드시 다른 고객이어야 한다
    owners = []
    with store._conn() as c:
        for qid in (first["id"], second["id"]):
            owners.append(c.execute("SELECT owner FROM job_queue WHERE id=?", (qid,)).fetchone()[0])
    assert set(owners) == {"7", "9"}, f"같은 고객이 두 자리를 먹었다: {owners}"
    # 7번이 아직 처리 중이므로 7번의 남은 1건은 아직 못 집는다
    assert store.claim_next() is None


def test_customer_slot_frees_after_finish(store):
    store.enqueue("render", {"customer_id": "7"})
    store.enqueue("render", {"customer_id": "7"})
    a = store.claim_next()
    assert store.claim_next() is None
    store.finish(a["id"], ok=True)
    assert store.claim_next() is not None, "앞 작업이 끝났는데 다음 건을 못 집는다"


def test_customer_facing_task_beats_background_task(store):
    store.enqueue("prewarm", {"customer_id": "1", "shortcode": "a"})   # 먼저 들어온 배경작업
    store.enqueue("render", {"customer_id": "2"})                      # 나중에 온 고객 대기작업
    got = store.claim_next()
    assert got["task"] == "render", "예열이 남의 렌더를 앞질렀다"


def test_owner_unknown_jobs_are_not_blocked(store):
    # 소유자를 알 수 없는 작업(수집 등)은 서로를 막지 않는다 — 하위호환
    store.enqueue("overseas", {})
    store.enqueue("overseas", {})
    assert store.claim_next() is not None
    assert store.claim_next() is not None


def test_owner_resolved_from_mix_job(store):
    """믹스 계열은 args에 customer_id가 없다 — job_id로 mix_jobs를 뒤져 소유자를 찾는다."""
    with store._conn() as c:
        try:
            c.execute("INSERT INTO mix_jobs(job_id, customer_id) VALUES('J1', 42)")
        except sqlite3.Error:
            pytest.skip("mix_jobs 스키마가 이 컬럼 구성이 아니다")
    store.enqueue("mix", {"job_id": "J1"})
    with store._conn() as c:
        assert c.execute("SELECT owner FROM job_queue WHERE task='mix'").fetchone()[0] == "42"
