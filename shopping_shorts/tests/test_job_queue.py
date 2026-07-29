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
