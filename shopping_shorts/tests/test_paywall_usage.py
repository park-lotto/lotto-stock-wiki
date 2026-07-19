"""유료게이트 Task3 — 계정별 일일 크레딧 상한 (2026-07-19)."""
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _s(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def test_usage_roundtrip(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.usage_get(1, "lens", "2026-07-19") == 0
    assert s.usage_incr(1, "lens", "2026-07-19") == 1
    assert s.usage_incr(1, "lens", "2026-07-19") == 2
    assert s.usage_get(1, "lens", "2026-07-19") == 2
    assert s.usage_get(1, "lens", "2026-07-20") == 0        # 날짜 독립
    assert s.usage_get(2, "lens", "2026-07-19") == 0        # 고객 독립


def test_check_and_count_daily_limit(tmp_path, monkeypatch):
    s = _s(tmp_path, monkeypatch)
    s.set_setting("limit_lens", 2)
    cid = s.create_customer("f", "pw12")
    s.set_plan(cid, "free", full_access_until=0)
    assert appmod.check_and_count(cid, "lens") is True     # 1
    assert appmod.check_and_count(cid, "lens") is True     # 2
    assert appmod.check_and_count(cid, "lens") is False    # 3 → 상한 초과
    assert appmod.check_and_count(cid, "render") is True   # op 독립(render 기본 2)


def test_pro_gets_higher_limit(tmp_path, monkeypatch):
    s = _s(tmp_path, monkeypatch)
    s.set_setting("limit_lens", 1)
    s.set_setting("limit_lens_pro", 3)
    cid = s.create_customer("p", "pw12")
    s.set_plan(cid, "pro")
    assert [appmod.check_and_count(cid, "lens") for _ in range(4)] == [True, True, True, False]


def test_admin_uses_pro_limit(tmp_path, monkeypatch):
    s = _s(tmp_path, monkeypatch)
    s.set_setting("limit_lens_pro", 2)
    assert appmod.check_and_count(0, "lens") is True        # 사장님=pro 상한
    assert appmod.check_and_count(0, "lens") is True
    assert appmod.check_and_count(0, "lens") is False


def test_global_incr_and_alert_counts(tmp_path, monkeypatch):
    s = _s(tmp_path, monkeypatch)
    s.set_setting("global_cap_lens", 1000)
    assert appmod.global_incr_and_alert("lens") == 1
    assert appmod.global_incr_and_alert("lens") == 2
