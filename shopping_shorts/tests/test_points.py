import subprocess  # noqa: F401  (repo 규약: 실프로세스 테스트는 stdin=DEVNULL — 여기선 불필요하나 패턴 유지 주석)
from shopping_shorts import points
from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_deduct_and_refund_roundtrip(tmp_path):
    st = _store(tmp_path)
    points.add(st, 7, 100)
    assert points.balance(st, 7) == 100
    assert points.deduct(st, 7, 30) is True
    assert points.balance(st, 7) == 70
    points.refund(st, 7, 30)
    assert points.balance(st, 7) == 100


def test_deduct_insufficient_returns_false_and_no_change(tmp_path):
    st = _store(tmp_path)
    points.add(st, 7, 10)
    assert points.deduct(st, 7, 30) is False
    assert points.balance(st, 7) == 10
