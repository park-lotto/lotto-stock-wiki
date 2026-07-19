"""유료게이트 Task1 — 접근권한 판정기 + /api/me (2026-07-19)."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _now():
    return int(datetime.now(timezone.utc).timestamp())


def test_access_level_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    cid = s.create_customer("u1", "pw12")
    s.set_plan(cid, "free", full_access_until=0)                      # 체험 만료
    assert appmod.access_level(cid, now=1000) == "ranking_only"
    s.set_plan(cid, "free", full_access_until=_now() + 86400)         # 체험 중
    assert appmod.access_level(cid) == "full"
    s.set_plan(cid, "pro")                                            # 결제
    assert appmod.access_level(cid, now=1000) == "full"
    assert appmod.access_level(0, now=1000) == "full"                 # 사장님
    assert appmod.access_level(99999, now=1000) == "ranking_only"     # 없는 고객


def test_create_customer_starts_trial(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("trial_days", 3)
    cid = s.create_customer("u2", "pw12")
    cust = s.get_customer(cid)
    assert cust["plan"] == "free"
    # 체험 만료가 대략 now+3일 (오차 여유 120초)
    assert abs(cust["full_access_until"] - (_now() + 3 * 86400)) < 120


def test_settings_roundtrip(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("trial_days", 7)
    s.set_setting("trial_days", 10)         # 덮어쓰기
    assert s.get_setting("trial_days") == "10"
    assert s.get_setting("nope", "d") == "d"


def test_api_me_auth_off_is_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", False)   # 미들웨어가 cid=0 세팅
    Store(str(tmp_path / "t.db")).ensure_paywall_schema()
    c = TestClient(appmod.app)
    d = c.get("/api/me").json()
    assert d["customer_id"] == 0 and d["level"] == "full" and d["plan"] == "pro"
    assert d["days_left"] is None
    assert d["limits"]["lens"] == 5 and d["limits"]["render"] == 2
