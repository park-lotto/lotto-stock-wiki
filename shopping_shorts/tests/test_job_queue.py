"""독립워커 작업큐(2026-07-29) — 배포 재시작에 안 죽는 실행기의 대기열."""
from shopping_shorts.store import Store


def test_enqueue_returns_id_and_claim_returns_it(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    qid = st.enqueue("mix", {"job_id": "j1"})
    assert isinstance(qid, int) and qid > 0
    got = st.claim_next()
    assert got["id"] == qid
    assert got["task"] == "mix"
    assert got["args"] == {"job_id": "j1"}


def test_claim_next_returns_none_when_empty(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    assert st.claim_next() is None


def test_claim_next_takes_oldest_first(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("mix", {"job_id": "first"})
    st.enqueue("render", {"job_id": "second"})
    assert st.claim_next()["args"]["job_id"] == "first"
    assert st.claim_next()["args"]["job_id"] == "second"


def test_claim_next_never_hands_same_job_twice(tmp_path):
    """워커가 둘이어도 같은 일을 두 번 집으면 안 된다 — claim은 원자적이어야 한다."""
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("mix", {"job_id": "only"})
    first = st.claim_next()
    second = st.claim_next()
    assert first is not None
    assert second is None


def test_finish_ok_marks_done(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    qid = st.enqueue("mix", {"job_id": "j1"})
    st.claim_next()
    st.finish(qid, True)
    assert st.queue_status("mix", {"job_id": "j1"})["state"] == "done"


def test_finish_fail_keeps_error(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    qid = st.enqueue("mix", {"job_id": "j1"})
    st.claim_next()
    st.finish(qid, False, "터졌음")
    got = st.queue_status("mix", {"job_id": "j1"})
    assert got["state"] == "failed"
    assert got["error"] == "터졌음"


def test_reap_stale_fails_only_dead_running(tmp_path):
    """heartbeat가 오래 멈춘 running만 failed로. 방금 뛴 건 안 건드린다."""
    import sqlite3
    st = Store(str(tmp_path / "t.db"))
    dead = st.enqueue("mix", {"job_id": "dead"})
    alive = st.enqueue("mix", {"job_id": "alive"})
    st.claim_next(); st.claim_next()
    con = sqlite3.connect(str(tmp_path / "t.db"))
    con.execute("UPDATE job_queue SET heartbeat_at=datetime('now','-10 minutes') WHERE id=?", (dead,))
    con.commit(); con.close()

    n = st.reap_stale(minutes=2)
    assert n == 1
    assert st.queue_status("mix", {"job_id": "dead"})["state"] == "failed"
    assert st.queue_status("mix", {"job_id": "alive"})["state"] == "running"


def test_heartbeat_keeps_job_alive(tmp_path):
    import sqlite3
    st = Store(str(tmp_path / "t.db"))
    qid = st.enqueue("mix", {"job_id": "j1"})
    st.claim_next()
    con = sqlite3.connect(str(tmp_path / "t.db"))
    con.execute("UPDATE job_queue SET heartbeat_at=datetime('now','-10 minutes') WHERE id=?", (qid,))
    con.commit(); con.close()

    st.heartbeat(qid)                 # 다시 뛴다
    assert st.reap_stale(minutes=2) == 0


def test_queue_status_position_counts_ahead(tmp_path):
    """내 앞에 대기·진행 중인 게 몇 개인지 — 화면 '앞에 N개 대기 중'용."""
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("mix", {"job_id": "a"})
    st.enqueue("mix", {"job_id": "b"})
    st.enqueue("mix", {"job_id": "c"})
    assert st.queue_status("mix", {"job_id": "a"})["position"] == 0
    assert st.queue_status("mix", {"job_id": "c"})["position"] == 2


def test_queue_status_none_when_absent(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    assert st.queue_status("mix", {"job_id": "없음"}) is None
