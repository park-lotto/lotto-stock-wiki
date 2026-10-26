"""관제 272 — 새 주소에서 화면을 열면 하루 한 번 옛 주소에 같은 로그인을 심고 돌아온다(고객 할 일 없음)."""
import urllib.parse
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store

NAV = {"sec-fetch-mode": "navigate", "accept": "text/html"}


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


def test_new_host_page_bounces_once_via_old_host(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app, base_url="https://stmaker.kr", cookies={"dash_auth": _cookie(0)})
    r = c.get("/produce?work=abc", headers=NAV, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://shoppingshorts.duckdns.org/grab_auth_sync?")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
    assert q["next"] == ["https://stmaker.kr/produce?work=abc"]
    assert "ss_oldsync" in r.headers.get("set-cookie", "")
    # 표시가 있으면 다시 안 들른다(무한 왕복 없음)
    c.cookies.set("ss_oldsync", "1")
    r2 = c.get("/produce?work=abc", headers=NAV, follow_redirects=False)
    assert r2.status_code != 302 or "grab_auth_sync" not in r2.headers.get("location", "")


def test_api_and_old_host_never_bounce(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app, base_url="https://stmaker.kr", cookies={"dash_auth": _cookie(0)})
    assert "grab_auth_sync" not in c.get("/api/me", follow_redirects=False).headers.get("location", "")
    old = TestClient(appmod.app, base_url="https://shoppingshorts.duckdns.org", cookies={"dash_auth": _cookie(0)})
    assert "grab_auth_sync" not in old.get("/produce", headers=NAV, follow_redirects=False).headers.get("location", "")


def test_old_host_endpoint_sets_login_and_device(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    t = appmod._old_sync_token(7, "dev123")
    old = TestClient(appmod.app, base_url="https://shoppingshorts.duckdns.org")
    r = old.get("/grab_auth_sync", params={"t": t, "next": "https://stmaker.kr/produce"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://stmaker.kr/produce"
    sc = r.headers.get("set-cookie", "")
    assert "dash_auth=" in sc and "ss_pc=dev123" in sc
    ck = sc.split("dash_auth=")[1].split(";")[0].strip('"')
    assert appmod._verify_session(ck) == 7


def test_bad_token_or_foreign_next_sets_nothing(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    old = TestClient(appmod.app, base_url="https://shoppingshorts.duckdns.org")
    r = old.get("/grab_auth_sync", params={"t": "7:9999999999:-:bad", "next": "https://evil.example/"},
                follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://stmaker.kr/"
    assert "dash_auth" not in r.headers.get("set-cookie", "")
    # 표는 세션 쿠키로 못 쓴다
    assert appmod._verify_session(appmod._old_sync_token(7, "d")) is None
