"""★자동저장이 방금 저장한 자막줄을 덮던 레이스 (2026-09-09 사장님/고객 제보).

편집안을 고치는 API는 전부 「읽고 → 고치고 → 통째로 다시 쓴다」인데,
장면 실험실 자동저장(scene_lab/apply)은 사람이 안 눌러도 계속 돈다.
실측 로그(job 593f4191557d): caplines 14:40:29 / apply 14:40:30 / caplines 14:40:33 / apply 14:40:34.
자동저장이 **읽은 뒤 쓰기 전** 사이에 줄 저장이 끼면 옛 편집안이 덮어써서
방금 저장한 줄이 사라진다(둘 다 200 OK라 화면엔 "저장했어요"만 뜬다).

이 테스트는 잠금이 그 겹침을 실제로 막는지 **스레드로 돌려서** 본다.
"""
import threading
import time

from shopping_shorts import app as _app


def test_plan_lock_is_per_job_and_serializes():
    """같은 job은 직렬화, 다른 job은 서로 안 막는다."""
    assert _app._plan_lock("A") is _app._plan_lock("A")
    assert _app._plan_lock("A") is not _app._plan_lock("B")


def test_read_modify_write_cannot_interleave():
    """잠금 없이 하면 옛 값이 덮어쓴다 — 잠금이 있으면 안 덮는다(같은 코드로 대조)."""
    def run(use_lock):
        db = {"lines": ["원래"]}
        def autosave():                    # 자동저장: 읽고 → 늦게 쓴다
            lock = _app._plan_lock("job1") if use_lock else None
            if lock:
                lock.acquire()
            try:
                snapshot = list(db["lines"])   # 읽기
                time.sleep(0.05)               # 그 사이에 줄 저장이 끼어든다
                db["lines"] = snapshot         # 통째로 쓰기
            finally:
                if lock:
                    lock.release()
        def save_lines():                  # 사람이 누른 줄 저장
            lock = _app._plan_lock("job1") if use_lock else None
            if lock:
                lock.acquire()
            try:
                db["lines"] = ["사장님이", "나눈 줄"]
            finally:
                if lock:
                    lock.release()
        t = threading.Thread(target=autosave)
        t.start()
        time.sleep(0.02)
        save_lines()
        t.join()
        return db["lines"]

    assert run(use_lock=False) == ["원래"], "잠금 없이는 덮어써야 한다(재현 확인)"
    assert run(use_lock=True) == ["사장님이", "나눈 줄"], "잠금이 있으면 저장한 줄이 살아남아야 한다"


def test_plan_writing_endpoints_take_the_lock():
    """편집안을 통째로 다시 쓰는 API가 잠금을 거치는지 — 새 경로가 생겨도 여기서 걸린다."""
    import inspect
    src = inspect.getsource(_app)
    for fn in ("api_mix_scene_lab_apply", "api_produce_mix_caplines", "api_produce_mix_cappos"):
        i = src.index("def %s(" % fn)
        body = src[i:i + 1500]
        assert "_plan_lock(" in body, "%s 가 편집안 잠금을 안 쓴다" % fn


def test_plan_path_detection():
    """어느 경로를 직렬화하는지 — 편집안 고치는 문만 잡고 나머진 안 잡는다."""
    f = _app._plan_job_of_path
    assert f("/api/produce/mix/abc123/caplines") == "abc123"
    assert f("/api/produce/mix/abc123/cappos") == "abc123"
    assert f("/api/produce/mix/abc123/scenezoom") == "abc123"
    assert f("/api/mix/scene_lab/abc123/apply") == "abc123"
    assert f("/api/mix/tts/abc123/2/regen") is None      # 편집안 통째 저장이 아니다
    assert f("/api/produce/styles") is None
    assert f("/") is None


def test_same_job_serialized_different_jobs_not():
    """미들웨어 잠금이 job별인지 — 다른 작업이 서로 막히면 화면이 느려진다."""
    import asyncio as _a
    _app._PLAN_REQ_LOCKS.clear()

    async def main():
        order = []

        async def req(job, tag, hold):
            lock = _app._PLAN_REQ_LOCKS.setdefault(job, _a.Lock())
            async with lock:
                order.append("시작:" + tag)
                await _a.sleep(hold)
                order.append("끝:" + tag)

        await _a.gather(req("J1", "A", 0.05), req("J1", "B", 0.01), req("J2", "C", 0.01))
        return order

    order = _a.run(main())
    # 같은 job의 A와 B는 절대 겹치지 않는다
    assert order.index("끝:A") < order.index("시작:B"), order
    # 다른 job인 C는 A가 붙잡고 있어도 먼저 끝난다
    assert order.index("끝:C") < order.index("끝:A"), order
