"""포인트 차감 — 어디에 썼는지 남고, 실패하면 돌려받는다."""
import pytest
from shopping_shorts import points
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_deduct_records_reason(store):
    """★어디에 썼는지가 남아야 정산·문의 대응이 된다."""
    points.add(store, 1, 1000)
    assert points.deduct(store, 1, 500, "vmake") is True
    rows = store.points_history(1)
    assert rows[0]["reason"] == "vmake"


def test_deduct_reduces_balance(store):
    points.add(store, 1, 1000)
    points.deduct(store, 1, 500, "vmake")
    assert points.balance(store, 1) == 500


def test_deduct_blocked_when_short(store):
    points.add(store, 1, 300)
    assert points.deduct(store, 1, 500, "vmake") is False
    assert points.balance(store, 1) == 300      # 안 깎였나


def test_exact_balance_is_allowed(store):
    """딱 맞으면 써져야 한다 — 잔액 0으로 끝나는 건 정상."""
    points.add(store, 1, 500)
    assert points.deduct(store, 1, 500, "vmake") is True
    assert points.balance(store, 1) == 0


def test_refund_restores(store):
    points.add(store, 1, 1000)
    points.deduct(store, 1, 500, "vmake")
    points.refund(store, 1, 500, "vmake")
    assert points.balance(store, 1) == 1000


def test_refund_reason_is_marked(store):
    """환불인지 충전인지 구분돼야 한다."""
    points.add(store, 1, 1000)
    points.refund(store, 1, 500, "vmake")
    assert store.points_history(1)[0]["reason"] == "vmake_refund"


def test_zero_cost_does_not_write(store):
    """무료 작업이 원장을 더럽히면 안 된다."""
    points.add(store, 1, 1000)
    assert points.deduct(store, 1, 0, "free") is True
    assert len(store.points_history(1)) == 1     # 충전 1건뿐


def test_fx_render_still_works(store):
    """★기존 고급효과 렌더가 안 깨져야 한다(reason 인자 없이 호출)."""
    points.add(store, 1, 1000)
    assert points.deduct(store, 1, 10) is True
    assert store.points_history(1)[0]["reason"] == "fx_render"


def test_history_is_newest_first(store):
    points.add(store, 1, 1000)
    points.deduct(store, 1, 100, "lens")
    points.deduct(store, 1, 500, "vmake")
    reasons = [r["reason"] for r in store.points_history(1)]
    assert reasons[:2] == ["vmake", "lens"]
