# -*- coding: utf-8 -*-
"""관리자(owner '0') 동시 2개 허용 + 큐 대기 조회 (2026-08-06 사장님)."""
import json
from shopping_shorts.store import Store


def _mk(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_관리자는_동시_2개까지_집는다(tmp_path):
    s = _mk(tmp_path)
    for i in range(3):
        s.enqueue("mix", {"job_id": f"j{i}", "customer_id": 0})
    a = s.claim_next(); b = s.claim_next(); c = s.claim_next()
    assert a and b, (a, b)          # 관리자 2개 동시 OK
    assert c is None                # 3개째는 대기 (기본 ADMIN_CONCURRENT_JOBS=2)


def test_일반고객은_여전히_1개(tmp_path):
    s = _mk(tmp_path)
    for i in range(2):
        s.enqueue("mix", {"job_id": f"j{i}", "customer_id": 7})
    a = s.claim_next(); b = s.claim_next()
    assert a and b is None, (a, b)


def test_mix_queue_ahead(tmp_path):
    s = _mk(tmp_path)
    s.enqueue("mix", {"job_id": "j0", "customer_id": 7})
    s.enqueue("mix", {"job_id": "j1", "customer_id": 7})
    assert s.mix_queue_ahead("j1") == 1     # 앞에 1개
    s.claim_next()                          # j0 집힘
    assert s.mix_queue_ahead("j1") == 0     # 다음 차례
    assert s.mix_queue_ahead("j0") is None  # running은 대기 아님


def test_mix_queue_ahead_ignores_other_tasks(tmp_path):
    """★"내 앞 13개"가 실제 기다림과 안 맞던 원인(2026-08-27 사장님 제보).

    전엔 종류를 안 가리고 queued를 전부 셌다. 실측 큐의 대부분은 `prewarm`
    (영상 미리받기, 보통 1초 안에 끝난다) — 그걸 "내 앞 작업"이라고 세면
    몇 초면 될 일을 열세 번 기다려야 하는 것처럼 보인다.
    """
    s = _mk(tmp_path)
    for i in range(5):
        s.enqueue("prewarm", {"shortcode": f"p{i}"})
    s.enqueue("mix", {"job_id": "j1", "customer_id": 7})
    assert s.mix_queue_ahead("j1") == 0     # prewarm 5개는 내 앞이 아니다


def test_mix_queue_ahead_follows_worker_order(tmp_path):
    """워커는 prio가 높은 것부터 집는다 — 세는 기준도 같아야 한다.

    id만 보면 "내 뒤"에 들어온 급한 작업이 실제로는 먼저 나가는데도
    앞 개수에 안 잡혀, 표시된 순번보다 오래 기다리게 된다.
    """
    s = _mk(tmp_path)
    s.enqueue("mix", {"job_id": "j1", "customer_id": 7})
    s.enqueue("mix", {"job_id": "j2", "customer_id": 8}, prio=10)   # 나중에 왔지만 우선
    assert s.mix_queue_ahead("j1") == 1
    assert s.mix_queue_ahead("j2") == 0
