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


# ── 영상제작 포인트 환불 (2026-08-17 리뷰 지적) ──
# 이 코드베이스의 규칙은 "실패하면 돌려준다" — 크레딧도(_refund_render_charge),
# 자막제거 포인트도(_refund_clean). 영상제작 포인트(3P)만 빠져 있어 가장 비싼
# 작업이 실패할 때 잔액이 조용히 갉히고 있었다.

def test_mix_points_refunded_on_failure(store):
    from shopping_shorts import pricing
    points.add(store, 7, 1000)
    mp._refund_mix_points(store, 7, "2026-08-17")
    assert points.balance(store, 7) == 1000 + pricing.cost(store, pricing.OP_MIX)


def test_mix_refund_skipped_without_charge_mark(store):
    """★render_charge_day가 없으면 과금 안 한 job이다 — 환불하면 잔액이 부푼다.
    produce 2단계·auto_run·retype이 이 경우에 해당한다."""
    points.add(store, 7, 1000)
    mp._refund_mix_points(store, 7, None)
    assert points.balance(store, 7) == 1000


def test_mix_refund_skips_owner(store):
    """사장님(cid 0)은 애초에 과금되지 않았다."""
    before = points.balance(store, 0)
    mp._refund_mix_points(store, 0, "2026-08-17")
    assert points.balance(store, 0) == before


def test_mix_refund_skips_user_key_holder(store):
    """★자기 키를 쓰는 사람은 안 깎였으니 환불하면 없던 포인트가 생긴다."""
    from shopping_shorts import keyroute
    store.add_customer_key(9, keyroute.SVC_GEMINI, "mykey")
    points.add(store, 9, 500)
    mp._refund_mix_points(store, 9, "2026-08-17")
    assert points.balance(store, 9) == 500
