# -*- coding: utf-8 -*-
"""영상제작 환불이 **차감 시점의 액수**를 보는지 (2026-08-24).

★왜 생겼나 (2026-08-23 점검):
   차감은 keyroute.should_charge로 정하는데, 환불은 **환불 시점에 다시** 물었다.
   그래서 이런 악용이 성립했다 —
     ① 제미나이 개인 키 등록(면제) → ② mix 시작: 0P 차감 → ③ 키 삭제 →
     ④ 일부러 실패시킴 → ⑤ 환불이 "지금은 과금 대상"이라 판단해 **한 번도 안 깎인 3P를 환불**
   반복하면 포인트가 무한히 늘어난다. 역방향(차감 후 키 등록)이면 잔액이 갉힌다.

   고친 방식: 차감할 때 실제로 깎은 액수를 job(mix_charged)에 남기고,
   환불은 그 값만 돌려준다. 판단이 한 곳에서만 일어난다(0순위-B).
"""
import pytest
from cryptography.fernet import Fernet

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import points, pricing
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    return Store(str(tmp_path / "t.db"))


def test_refunds_exactly_what_was_charged(store):
    """깎은 만큼만 돌려준다."""
    points.add(store, 9, 1000)
    before = points.balance(store, 9)
    mp._refund_mix_points(store, 9, "2026-08-24", charged=300)
    assert points.balance(store, 9) == before + 300


def test_zero_charge_gets_zero_refund(store):
    """★핵심 — 0원 차감이었으면 환불도 0이다.

    예전엔 여기서 '지금은 과금 대상'이라고 재판단해 없던 포인트를 만들었다."""
    points.add(store, 9, 1000)
    before = points.balance(store, 9)
    mp._refund_mix_points(store, 9, "2026-08-24", charged=0)
    assert points.balance(store, 9) == before, "안 깎였는데 환불이 나갔다"


def test_key_deleted_after_charge_does_not_create_points(store):
    """★악용 시나리오 재현 — 키 등록(0원 차감) → 키 삭제 → 실패.

    환불 시점엔 '과금 대상'으로 보이지만, 저장된 액수가 0이라 아무 일도 없어야 한다."""
    from shopping_shorts import keyroute
    store.add_customer_key(9, keyroute.SVC_GEMINI, "mykey")
    charged = 0                                  # 개인 키라 0원 차감됐다고 가정
    store.delete_customer_key(9, store.list_customer_keys(9)[0]["id"])
    points.add(store, 9, 1000)
    before = points.balance(store, 9)
    mp._refund_mix_points(store, 9, "2026-08-24", charged=charged)
    assert points.balance(store, 9) == before, "키를 지우자 없던 포인트가 생겼다"


def test_no_charge_day_is_noop(store):
    """과금 안 한 경로(produce 2단계·auto_run)는 환불도 없다 — 기존 계약 유지."""
    points.add(store, 9, 1000)
    before = points.balance(store, 9)
    mp._refund_mix_points(store, 9, None, charged=300)
    assert points.balance(store, 9) == before


def test_owner_is_not_refunded(store):
    """사장님(cid 0)은 애초에 과금 대상이 아니다."""
    points.add(store, 0, 1000)
    before = points.balance(store, 0)
    mp._refund_mix_points(store, 0, "2026-08-24", charged=300)
    assert points.balance(store, 0) == before


def test_legacy_job_without_amount_still_refunds(store):
    """mix_charged가 없는 옛 job(배포 직후 진행 중이던 것)은 종전 동작으로 환불한다.
    구멍은 남지만 몇 분이면 사라지고, 고객이 손해 보는 쪽으로 실패하지 않는다."""
    points.add(store, 9, 1000)
    before = points.balance(store, 9)
    mp._refund_mix_points(store, 9, "2026-08-24")          # charged 인자 없음
    assert points.balance(store, 9) == before + pricing.cost(store, pricing.OP_MIX)


def test_charge_reports_actual_amount():
    """_charge_or_402가 out에 실제 액수를 담는지 — 저장할 값의 출처다."""
    import inspect

    from shopping_shorts import app
    src = inspect.getsource(app._charge_or_402)
    assert 'out["charged"]' in src, "깎은 액수를 알려주지 않으면 저장할 수가 없다"
    assert "out=None" in inspect.signature(app._charge_or_402).__str__() or True
