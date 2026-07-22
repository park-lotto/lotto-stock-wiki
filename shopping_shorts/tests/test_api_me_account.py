"""/api/me 계정 패널 필드(2026-07-22) — 사이드바 계정 카드가 쓰는 데이터."""
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


def test_me_admin_fields(tmp_path, monkeypatch):
    """관리자(cid0)=is_admin·이메일 '관리자'·사용량 없음(무제한)."""
    _setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    d = c.get("/api/me").json()
    assert d["is_admin"] is True
    assert d["email"] == "관리자"
    assert d["usage"] is None                      # 무제한 → 사용량 표시 안 함


def test_me_pro_user_fields(tmp_path, monkeypatch):
    """pro 유저=이메일·오늘 사용량·상한·가입일수 제공."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("prouser", "pw12")
    s.set_plan(cid, "pro")
    with s._conn() as conn:
        conn.execute("UPDATE customers SET email=? WHERE id=?", ("me@gmail.com", cid))
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    d = c.get("/api/me").json()
    assert d["is_admin"] is False
    assert d["email"] == "me@gmail.com"
    assert set(d["usage"].keys()) == {"lens", "render", "script"}
    assert d["usage_limits"]["lens"] is not None    # 상한 숫자 제공
    assert isinstance(d["member_days"], int) and d["member_days"] >= 1
