"""전역 발음사전 CRUD API(2026-07-22). 관리자(customer_id==0) 전용.

인증 우회 패턴은 test_paywall_admin.py를 그대로 따른다: _AUTH_ON=True로 켜고
_sign_session(0, ...)으로 서명한 dash_auth 쿠키를 관리자 세션으로 쓴다
(request.state.customer_id는 _auth_guard 미들웨어가 이 쿠키를 검증해 채운다 — app.py:3731-3733).
"""
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


def test_post_then_get_roundtrip(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/pron/global", json={"phrase": "좋은데요", "respelling": "조은데요"})
    assert r.status_code == 200 and r.json()["ok"] is True
    got = owner.get("/api/pron/global").json()["entries"]
    assert {"phrase": "좋은데요", "respelling": "조은데요"} in got


def test_reject_empty_or_noop(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    assert owner.post("/api/pron/global", json={"phrase": "", "respelling": "x"}).status_code == 400
    assert owner.post("/api/pron/global", json={"phrase": "가", "respelling": "가"}).status_code == 400


def test_delete_removes(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    owner.post("/api/pron/global", json={"phrase": "AS", "respelling": "에이에스"})
    assert owner.delete("/api/pron/global/AS").json()["ok"] is True
    assert all(e["phrase"] != "AS" for e in owner.get("/api/pron/global").json()["entries"])


def test_non_admin_forbidden(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert other.get("/api/pron/global").status_code == 403
    assert other.post("/api/pron/global", json={"phrase": "a", "respelling": "b"}).status_code == 403
    assert other.delete("/api/pron/global/a").status_code == 403
