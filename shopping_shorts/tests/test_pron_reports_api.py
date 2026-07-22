"""발음 제보 API(2026-07-22). 관리자 전용.

인증 우회 패턴은 test_pron_api.py를 그대로 복제한다: _AUTH_ON=True로 켜고
_sign_session(0, ...)으로 서명한 dash_auth 쿠키를 관리자 세션으로 쓴다
(request.state.customer_id는 _auth_guard 미들웨어가 이 쿠키를 검증해 채운다).
test_pron_api.py는 admin/non-admin 클라이언트를 fixture로 노출하지 않으므로
같은 헬퍼(_cookie/_setup)를 이 파일에도 복제해서 쓴다.
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


def test_report_roundtrip(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    admin = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = admin.post("/api/pron/report", json={"text": "좋은데요", "comment": "이상"})
    assert r.status_code == 200 and r.json()["ok"] is True
    rid = r.json()["id"]
    reports = admin.get("/api/pron/reports").json()["reports"]
    assert any(x["id"] == rid and x["text"] == "좋은데요" and x["comment"] == "이상" for x in reports)


def test_report_empty_text_400(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    admin = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    assert admin.post("/api/pron/report", json={"text": "  ", "comment": "x"}).status_code == 400


def test_resolve_removes_from_list(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    admin = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    rid = admin.post("/api/pron/report", json={"text": "가치", "comment": ""}).json()["id"]
    assert admin.post(f"/api/pron/reports/{rid}/resolve").json()["ok"] is True
    assert all(x["id"] != rid for x in admin.get("/api/pron/reports").json()["reports"])


def test_non_admin_forbidden(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert other.get("/api/pron/reports").status_code == 403
    assert other.post("/api/pron/report", json={"text": "a", "comment": ""}).status_code == 403
