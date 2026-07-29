"""워커 루프(2026-07-29) — 한 번에 하나씩, 실패해도 워커는 안 죽는다."""
import json

from shopping_shorts import worker, overseas_hot_jobs
from shopping_shorts.store import Store


def test_run_one_returns_false_when_queue_empty(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    assert worker.run_one(st) is False


def test_run_one_executes_task_and_marks_done(tmp_path, monkeypatch):
    st = Store(str(tmp_path / "t.db"))
    called = []
    monkeypatch.setitem(worker.TASKS, "mix", lambda a: called.append(a["job_id"]))
    st.enqueue("mix", {"job_id": "j1"})

    assert worker.run_one(st) is True
    assert called == ["j1"]
    assert st.queue_status("mix", {"job_id": "j1"})["state"] == "done"


def test_worker_survives_task_exception(tmp_path, monkeypatch):
    """작업이 터져도 워커는 죽지 않고 failed로 기록만 남긴다."""
    st = Store(str(tmp_path / "t.db"))
    def boom(a):
        raise RuntimeError("펑")
    monkeypatch.setitem(worker.TASKS, "mix", boom)
    st.enqueue("mix", {"job_id": "j1"})

    assert worker.run_one(st) is True          # 예외가 밖으로 안 샌다
    got = st.queue_status("mix", {"job_id": "j1"})
    assert got["state"] == "failed"
    assert "펑" in got["error"]


def test_unknown_task_fails_gracefully(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("없는작업", {})
    assert worker.run_one(st) is True
    assert st.queue_status("없는작업")["state"] == "failed"


def test_run_one_processes_one_at_a_time(tmp_path, monkeypatch):
    """1GB 서버라 동시 실행은 금물 — 한 번 호출에 딱 하나만 처리한다."""
    st = Store(str(tmp_path / "t.db"))
    done = []
    monkeypatch.setitem(worker.TASKS, "mix", lambda a: done.append(a["job_id"]))
    st.enqueue("mix", {"job_id": "a"})
    st.enqueue("mix", {"job_id": "b"})

    worker.run_one(st)
    assert done == ["a"]


def test_progress_readers_overseas_reflects_job_state():
    """워커 프로세스 안의 overseas_hot_jobs._JOB을 읽어 phase·count를 JSON으로 실어보낸다
    (2026-07-29 Critical fix — 서버 프로세스의 같은 이름 전역과는 별개 메모리)."""
    overseas_hot_jobs._JOB.update(phase="수집·자막판정 신규15·캐시15", count=7)
    got = json.loads(worker.PROGRESS_READERS["overseas"]())
    assert got == {"phase": "수집·자막판정 신규15·캐시15", "count": 7}


def test_beat_reader_exception_does_not_kill_heartbeat(tmp_path, monkeypatch):
    """진행정보 읽기가 터져도 heartbeat 자체는 계속 뛰어야 한다(생존신호 > 진행표시)."""
    st = Store(str(tmp_path / "t.db"))
    qid = st.enqueue("overseas", {})
    st.claim_next()

    def boom():
        raise RuntimeError("읽기 실패")
    monkeypatch.setitem(worker.PROGRESS_READERS, "overseas", boom)

    reader = worker.PROGRESS_READERS.get("overseas")
    progress = None
    try:
        progress = reader()
    except Exception:
        progress = None
    st.heartbeat(qid, progress)   # 예외 없이 하트비트가 찍혀야 함
    got = st.queue_status("overseas", {})
    assert got["state"] == "running"
