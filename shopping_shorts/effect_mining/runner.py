"""One-shot and continuous runners for mining schedulers and workers."""

from __future__ import annotations

import logging
import threading
import time


log = logging.getLogger("effect-mining")


def scheduler_tick(db, now=None):
    return {
        "recovered": db.recover_expired_leases(now=now),
        "scheduled_sources": db.schedule_due_sources(now=now),
    }


def worker_tick(db, pipeline, worker_id, tasks=None, now=None, lease_sec=900,
                base_backoff_sec=30, max_backoff_sec=3600):
    job = db.claim(worker_id, lease_sec=lease_sec, tasks=tasks, now=now)
    if job is None:
        return None

    stop = threading.Event()
    beater = None
    if now is None:
        def beat():
            while not stop.wait(max(5, int(lease_sec) // 3)):
                if not db.heartbeat(job["id"], worker_id, lease_sec=lease_sec):
                    log.error("lost mining job lease job_id=%s", job["id"])
                    return

        beater = threading.Thread(target=beat, daemon=True)
        beater.start()

    try:
        result = pipeline.execute(job["task"], job["payload"], now=now)
        db.complete(job["id"], worker_id, result, now=now)
        state = "done"
    except Exception as exc:  # worker process must survive a single bad source/item
        log.exception("mining job failed job_id=%s task=%s", job["id"], job["task"])
        state = db.fail(
            job["id"], worker_id, repr(exc), now=now,
            base_backoff_sec=base_backoff_sec, max_backoff_sec=max_backoff_sec,
        )
    finally:
        stop.set()
        if beater is not None:
            beater.join(timeout=1)
    return {"job_id": job["id"], "task": job["task"], "state": state}


def run_scheduler_loop(db, poll_sec=15):
    while True:
        result = scheduler_tick(db)
        if result["recovered"] or result["scheduled_sources"]:
            log.info("scheduler tick %s", result)
        time.sleep(float(poll_sec))


def run_worker_loop(db, pipeline, worker_id, tasks=None, poll_sec=3, lease_sec=900):
    while True:
        result = worker_tick(db, pipeline, worker_id, tasks=tasks, lease_sec=lease_sec)
        if result is None:
            time.sleep(float(poll_sec))
        else:
            log.info("worker tick %s", result)
