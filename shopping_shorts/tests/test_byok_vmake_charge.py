"""자막제거 과금 — 소스 개수만큼 깎고, 캐시된 건 안 깎는다."""
import importlib
import pytest
from shopping_shorts import mix_pipeline as mp, keycrypt, points
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("vmake_api_key", "사장님키")
    return s


def test_charges_per_source(store, monkeypatch, tmp_path):
    """★소스 3개면 VMake가 3번 돈다 = 15P(1500). job당 1회가 아니다."""
    points.add(store, 5, 10000)
    charged = mp._charge_clean(store, 5, 3)
    assert charged == 1500
    assert points.balance(store, 5) == 8500


def test_blocked_when_short(store):
    """잔액이 모자라면 아예 시작하지 않는다 — 반만 청소되면 안 된다."""
    points.add(store, 5, 1000)          # 10P — 소스 3개(15P)엔 부족
    with pytest.raises(mp.NotEnoughPoints):
        mp._charge_clean(store, 5, 3)
    assert points.balance(store, 5) == 1000     # 안 깎였나


def test_user_key_is_free(store, monkeypatch):
    """★내 VMake 키를 등록했으면 한 푼도 안 깎인다."""
    points.add(store, 5, 10000)
    store.add_customer_key(5, "vmake", "내키")
    assert mp._charge_clean(store, 5, 3) == 0
    assert points.balance(store, 5) == 10000


def test_zero_sources_is_free(store):
    """전부 캐시돼 청소할 게 없으면 과금 0."""
    points.add(store, 5, 10000)
    assert mp._charge_clean(store, 5, 0) == 0
    assert points.balance(store, 5) == 10000


def test_refund_on_failure(store):
    points.add(store, 5, 10000)
    mp._charge_clean(store, 5, 2)
    assert points.balance(store, 5) == 9000
    mp._refund_clean(store, 5, 1000)
    assert points.balance(store, 5) == 10000


def test_owner_is_not_charged(store):
    """사장님 본인(cid 0)은 자기 키를 쓰므로 과금 대상이 아니다."""
    assert mp._charge_clean(store, 0, 3) == 0
