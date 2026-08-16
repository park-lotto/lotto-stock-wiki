"""포인트 차감 — 어디에 썼는지 남고, 실패하면 돌려받는다."""
import threading

import pytest
from shopping_shorts import points
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_concurrent_deduct_cannot_overdraw(tmp_path):
    """★워커 여러 개가 동시에 깎아도 잔액이 음수가 되면 안 된다.

    실사고 재현(2026-08-17): 판정과 차감이 SQL 두 문장으로 갈려 있으면
    워커들이 같은 잔액을 읽고 전부 통과한다. 실측으로 10P에 5P 차감 5개를
    던졌더니 3건이 성공해 잔액이 -5P가 됐다. 자막제거는 소스 3개면 15P를
    한 번에 깎으므로 피해가 크다 — 이 테스트가 재발을 막는다."""
    db = str(tmp_path / "race.db")
    seed = Store(db)
    points.add(seed, 1, 1000)                  # 10P → 5P짜리 2건만 가능

    results, lock = [], threading.Lock()

    def worker():
        ok = points.deduct(Store(db), 1, 500, "vmake")
        with lock:
            results.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(results) == 2, "잔액상 2건만 성공해야 한다"
    assert points.balance(seed, 1) == 0, "잔액이 음수가 되면 안 된다"


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
