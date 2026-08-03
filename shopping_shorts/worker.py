"""독립워커 - 긴 작업을 FastAPI 서버 프로세스 밖에서 실행한다(2026-07-29).

왜 있나: 예전엔 믹스, 해외HOT 수집이 서버 안 BackgroundTasks로 돌아서, 배포의
`systemctl restart shopping-shorts`가 진행 중 작업을 SIGKILL했다. 화면은 실패도 못 띄우고
조용히 멈췄다(2026-07-29 실사고, 하루 3건). 이제 서버는 큐에 넣기만 하고 여기서 실행한다.

1GB 서버라 한 번에 하나씩만 돈다. 서버를 키우면 이 유닛을 복제해 띄우면 된다
(claim_next가 원자적이라 같은 작업을 두 번 집지 않는다).
"""
import json
import logging
import threading
import time

from shopping_shorts import mix_pipeline, overseas_hot_jobs, prewarm
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store

log = logging.getLogger("worker")

_MIX_WORK_DIR = DB_PATH.parent / "mix_jobs"

POLL_SEC = 5           # 큐가 비었을 때 다시 볼 때까지
HEARTBEAT_SEC = 30     # 살아있다는 신호 주기(reap_stale 2분보다 충분히 짧게)

TASKS = {
    "mix":      lambda a: mix_pipeline.run_mix_job(a["job_id"], DB_PATH, _MIX_WORK_DIR),
    "retype":   lambda a: mix_pipeline.retype_mix_job(a["job_id"], a["video_type"],
                                                      DB_PATH, _MIX_WORK_DIR),
    "render":   lambda a: mix_pipeline.run_render(a["job_id"], DB_PATH, _MIX_WORK_DIR),
    "preview":  lambda a: mix_pipeline.run_preview(a["job_id"], DB_PATH, _MIX_WORK_DIR),
    "clean":    lambda a: mix_pipeline.run_clean_sources(a["job_id"], DB_PATH, _MIX_WORK_DIR),
    "overseas": lambda a: overseas_hot_jobs._run(),
    # 담기 시 사전분석 예열(2026-07-30) — 제작소 1단계 로딩 제거용. 실패해도 무해하다
    # (run_prewarm이 예외를 안 던지고 상태 문자열만 돌려준다).
    "prewarm":  lambda a: prewarm.run_prewarm(
        a.get("shortcode"), a.get("url"), caption=a.get("caption") or "",
        customer_id=a.get("customer_id") or "0", video_url=a.get("video_url") or "",
        category=a.get("category")),
}

# 진행 문구(phase·count)를 큐로 실어 보내는 리더 — 워커 프로세스 안에서만 읽을 수 있다
# (서버 프로세스의 같은 이름 전역변수는 별개 메모리다, 2026-07-29 Critical fix).
PROGRESS_READERS = {
    # 워커 프로세스 안에서는 이 _JOB이 '진짜'다 — 서버 프로세스 것과는 별개다.
    "overseas": lambda: json.dumps(
        {"phase": overseas_hot_jobs._JOB["phase"], "count": overseas_hot_jobs._JOB["count"]},
        ensure_ascii=False),
}


def run_one(store):
    """대기 작업 하나를 실행한다. 처리했으면 True, 큐가 비었으면 False.

    작업이 터져도 예외를 밖으로 내보내지 않는다 - 워커가 죽으면 큐 전체가 멈춘다."""
    job = store.claim_next()
    if not job:
        return False
    qid, task, args = job["id"], job["task"], job["args"]
    stop = threading.Event()

    def _beat():
        reader = PROGRESS_READERS.get(task)
        while not stop.wait(HEARTBEAT_SEC):
            progress = None
            if reader is not None:
                try:
                    progress = reader()
                except Exception:
                    log.exception("progress 읽기 실패 qid=%s task=%s", qid, task)
            try:
                store.heartbeat(qid, progress)
            except Exception:
                log.exception("heartbeat 실패 qid=%s", qid)

    beater = threading.Thread(target=_beat, daemon=True)
    beater.start()
    try:
        fn = TASKS.get(task)
        if fn is None:
            store.finish(qid, False, f"모르는 작업: {task}")
            return True
        log.info("작업 시작 qid=%s task=%s args=%s", qid, task, json.dumps(args, ensure_ascii=False))
        fn(args)
        store.finish(qid, True)
        log.info("작업 완료 qid=%s task=%s", qid, task)
    except Exception as e:
        log.exception("작업 실패 qid=%s task=%s", qid, task)
        store.finish(qid, False, repr(e))
    finally:
        stop.set()
    return True


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    store = Store(DB_PATH)
    log.info("워커 시작 - db=%s", DB_PATH)
    while True:
        try:
            store.reap_stale()
            if not run_one(store):
                time.sleep(POLL_SEC)
        except Exception:
            log.exception("워커 루프 오류 - 계속 돈다")
            time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
