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
