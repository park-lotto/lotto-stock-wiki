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


def test_empty_dash_pass_blocks_admin_backdoor(tmp_path, monkeypatch):
    """★CRITICAL: 구글만 켠 배포(DASH_PASS 빈값)에서 admin/빈비번으로 사장님 세션을 얻으면 안 된다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_PASS", "")
    monkeypatch.setattr(appmod, "DASH_SECRET", "sec")
    Store(str(tmp_path / "t.db")).ensure_paywall_schema()
    c = TestClient(appmod.app, follow_redirects=False)
    r = c.post("/api/login", data={"user": "admin", "pass": ""})
    assert "dash_auth" not in r.headers.get("set-cookie", "")   # 세션 안 생김
    assert "/login?e=1" in r.headers.get("location", "")


def test_admin_login_still_works_with_dash_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_PASS", "secretpw")
    monkeypatch.setattr(appmod, "DASH_USER", "admin")
    monkeypatch.setattr(appmod, "DASH_SECRET", "sec")
    Store(str(tmp_path / "t.db")).ensure_paywall_schema()
    c = TestClient(appmod.app, follow_redirects=False)
    r = c.post("/api/login", data={"user": "admin", "pass": "secretpw"})
    assert "dash_auth" in r.headers.get("set-cookie", "")       # 정상 admin 로그인


class _FakeResp:
    def __init__(self, code, data):
        self.status_code = code; self._d = data
    def json(self):
        return self._d


def test_unverified_email_stored_as_none():
    class FakeReq:
        def post(self, *a, **k): return _FakeResp(200, {"access_token": "AT"})
        def get(self, *a, **k): return _FakeResp(200, {"sub": "s1", "email": "e@x.com", "email_verified": False})
    ident = appmod._google_fetch_identity("code", _requests=FakeReq())
    assert ident["sub"] == "s1" and ident["email"] is None       # 미인증 이메일=신뢰 안 함


def test_verified_email_kept():
    class FakeReq:
        def post(self, *a, **k): return _FakeResp(200, {"access_token": "AT"})
        def get(self, *a, **k): return _FakeResp(200, {"sub": "s2", "email": "ok@x.com", "email_verified": True})
    ident = appmod._google_fetch_identity("code", _requests=FakeReq())
    assert ident["email"] == "ok@x.com"


def test_approved_at_column_and_backfill(tmp_path):
    import sqlite3
    from shopping_shorts.store import Store
    dbp = str(tmp_path / "t.db")
    s = Store(dbp)
    # 페이월 도입 전처럼 approved_at 없이 고객을 직접 INSERT(구버전 DB 재현)
    with sqlite3.connect(dbp) as c:
        c.execute("ALTER TABLE customers DROP COLUMN approved_at")  # 컬럼 제거해 구버전 재현
        c.execute("INSERT INTO customers(username, password_hash, salt, created_at, plan, full_access_until) "
                  "VALUES('old','h','s',datetime('now'),'free',0)")
    # 다시 스키마 보증 → 컬럼 재추가 + 기존 행 백필
    Store(dbp).ensure_paywall_schema()
    with sqlite3.connect(dbp) as c:
        row = c.execute("SELECT approved_at FROM customers WHERE username='old'").fetchone()
    assert row[0] is not None       # 기존 계정 = 승인됨(백필)


def test_create_customer_approved_flag(tmp_path):
    from shopping_shorts.store import Store
    s = Store(str(tmp_path / "t.db"))
    cid_ok = s.create_customer("appr", "pw12")                 # 기본 approved=True
    cust_ok = s.get_customer(cid_ok)
    assert cust_ok["approved_at"] is not None
    assert cust_ok["full_access_until"] > 0                     # 체험 시작됨
    cid_pend = s.create_customer("pend", "pw12", approved=False)
    cust_pend = s.get_customer(cid_pend)
    assert cust_pend["approved_at"] is None                     # 대기중
    assert cust_pend["full_access_until"] == 0                  # 체험 미시작
