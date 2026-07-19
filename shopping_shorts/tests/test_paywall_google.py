"""유료게이트 Task6 — 구글 OAuth 로그인 (2026-07-19). 네트워크는 mock."""
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def test_get_or_create_by_google(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid = s.get_or_create_by_google("sub-abc", "a@x.com")
    assert cid and s.get_customer(cid)["plan"] == "free"
    assert s.get_customer(cid)["email"] == "a@x.com"
    assert s.get_customer(cid)["full_access_until"] > 0          # 체험 자동시작
    assert s.get_or_create_by_google("sub-abc", "a@x.com") == cid  # 같은 sub=같은 계정
    assert s.get_or_create_by_google("sub-def", "b@x.com") != cid  # 다른 sub=다른 계정


def test_authorize_url_has_params(monkeypatch):
    monkeypatch.setattr(appmod, "GOOGLE_CLIENT_ID", "cid123")
    monkeypatch.setattr(appmod, "GOOGLE_REDIRECT_URI", "https://ex.com/cb")
    url = appmod._google_authorize_url("STATE9")
    assert "client_id=cid123" in url and "state=STATE9" in url
    assert "redirect_uri=https%3A%2F%2Fex.com%2Fcb" in url and "scope=openid" in url


def test_callback_rejects_state_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "DASH_SECRET", "sec")
    called = {"n": 0}
    monkeypatch.setattr(appmod, "_google_fetch_identity", lambda code: called.__setitem__("n", called["n"] + 1))
    c = TestClient(appmod.app, cookies={"g_state": "GOOD"})
    r = c.get("/auth/google/callback?code=X&state=EVIL", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]
    assert "dash_auth" not in r.headers.get("set-cookie", "")   # 세션 안 생김
    assert called["n"] == 0                                     # 토큰교환 시도조차 안 함


def test_callback_success_sets_session(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "DASH_SECRET", "sec")
    monkeypatch.setattr(appmod, "_google_fetch_identity",
                        lambda code: {"sub": "sub-xyz", "email": "u@x.com"})
    c = TestClient(appmod.app, cookies={"g_state": "S1"})
    r = c.get("/auth/google/callback?code=CODE&state=S1", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "dash_auth" in r.headers.get("set-cookie", "")       # 세션 생성됨
    # 그 sub의 고객이 DB에 생겼나
    cid = Store(str(tmp_path / "t.db")).get_or_create_by_google("sub-xyz")
    assert Store(str(tmp_path / "t.db")).get_customer(cid)["email"] == "u@x.com"


def test_callback_failed_identity_no_session(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "DASH_SECRET", "sec")
    monkeypatch.setattr(appmod, "_google_fetch_identity", lambda code: None)   # 인증 실패
    c = TestClient(appmod.app, cookies={"g_state": "S1"})
    r = c.get("/auth/google/callback?code=CODE&state=S1", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]
    assert "dash_auth" not in r.headers.get("set-cookie", "")


def test_login_page_has_google_button(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    c = TestClient(appmod.app)
    html = c.get("/login").text
    assert "/auth/google/login" in html and "Google" in html
