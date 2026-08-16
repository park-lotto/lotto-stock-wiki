"""단가표 — 내부는 100배 정수, 화면은 사람이 읽는 값."""
import pytest
from shopping_shorts import pricing
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_vmake_is_five_points(store):
    """자막제거 5P = 실비용 500원 ÷ (1P=100원). 유일하게 근거가 확실한 값."""
    assert pricing.cost(store, "vmake") == 500      # 5P × 100


def test_default_when_unset(store):
    assert pricing.cost(store, "mix") == 300        # 3P
    assert pricing.cost(store, "tts") == 100         # 1P
    assert pricing.cost(store, "lens") == 10         # 0.1P
    assert pricing.cost(store, "script") == 10       # 0.1P


def test_admin_override(store):
    """★배포 없이 숫자만 고칠 수 있어야 한다."""
    store.set_setting("point_cost_vmake", "700")
    assert pricing.cost(store, "vmake") == 700


def test_unknown_op_is_free(store):
    """모르는 작업에 임의 요금을 매기지 않는다 — 0이 안전한 기본값."""
    assert pricing.cost(store, "무료작업") == 0


def test_broken_setting_falls_back(store):
    """설정값이 깨져도 죽지 않고 기본값으로 돈다."""
    store.set_setting("point_cost_vmake", "이건숫자가아님")
    assert pricing.cost(store, "vmake") == 500


def test_negative_setting_is_ignored(store):
    """음수 단가는 충전이 돼버린다 — 막는다."""
    store.set_setting("point_cost_vmake", "-999")
    assert pricing.cost(store, "vmake") == 500


def test_to_display_converts_to_human(store):
    assert pricing.to_display(500) == 5
    assert pricing.to_display(10) == 0.1
    assert pricing.to_display(0) == 0


def test_display_drops_trailing_zero(store):
    """5.0P가 아니라 5P로 보여야 한다."""
    assert str(pricing.to_display(500)) == "5"
