"""유료게이트 Task4 — 관리자 승격·설정 페이지 (2026-07-19)."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def test_admin_requires_owner(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")            # 일반 고객(체험중=full)
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert other.get("/api/admin/customers").status_code == 403   # 관리자 아님
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    assert owner.get("/api/admin/customers").status_code == 200   # 사장님


def test_admin_set_plan_promotes(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u2", "pw12")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/admin/set_plan", json={"customer_id": cid, "plan": "pro"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert s.get_customer(cid)["plan"] == "pro"
    assert appmod.access_level(cid) == "full"
    # free로 내리면 즉시 ranking_only
    owner.post("/api/admin/set_plan", json={"customer_id": cid, "plan": "free"})
    assert appmod.access_level(cid) == "ranking_only"


def test_admin_customers_lists_with_usage(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u3", "pw12")
    s.usage_incr(cid, "lens", appmod._today_utc())
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    d = owner.get("/api/admin/customers").json()
    row = [c for c in d["customers"] if c["id"] == cid][0]
    assert row["usage"]["lens"] == 1 and row["level"] == "full"


def test_admin_settings_roundtrip(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/admin/settings", json={"trial_days": "3", "limit_lens": "9", "bogus": "x"})
    assert r.status_code == 200
    assert s.get_setting("trial_days") == "3" and s.get_setting("limit_lens") == "9"
    assert s.get_setting("bogus") is None       # 허용 키만 저장
