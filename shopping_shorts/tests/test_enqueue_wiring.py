"""서버가 직접 실행하지 않고 큐에 넣는지(2026-07-29 독립워커 전환)."""
import shopping_shorts.overseas_hot_jobs as job
from shopping_shorts.store import Store


def test_overseas_start_enqueues_instead_of_thread(monkeypatch, tmp_path):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(job, "DB_PATH", db)
    job._JOB.update(status="idle", phase="", count=0, error=None, started=0.0)
    monkeypatch.setattr(job.threading, "Thread",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("스레드를 띄우면 안 된다 — 큐에 넣어야 한다")))

    res = job.start()
    assert res["status"] == "running"
    st = Store(db)
    q = st.queue_status("overseas")
    assert q is not None and q["state"] == "queued"


def test_overseas_start_does_not_double_enqueue(monkeypatch, tmp_path):
    """이미 큐에 있으면 또 넣지 않는다 — 버튼 두 번 눌러도 한 번만 돈다."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(job, "DB_PATH", db)
    job._JOB.update(status="idle", phase="", count=0, error=None, started=0.0)
    job.start()
    job._JOB.update(status="idle", started=0.0)   # 메모리 상태를 지워도
    job.start()                                    # 큐를 보고 막아야 한다

    st = Store(db)
    with st._conn() as c:
        n = c.execute("SELECT COUNT(*) FROM job_queue WHERE task='overseas'").fetchone()[0]
    assert n == 1
