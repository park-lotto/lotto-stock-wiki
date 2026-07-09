from fastapi.testclient import TestClient
from shopping_shorts.app import app


def test_healthz():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


import shopping_shorts.app as app_module
from fastapi.testclient import TestClient


def _client_with_auth(monkeypatch, password="secret123"):
    monkeypatch.setattr(app_module, "DASH_PASS", password)
    monkeypatch.setattr(app_module, "DASH_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_AUTH_ON", True)
    return TestClient(app_module.app)


def test_auth_off_by_default(monkeypatch):
    """DASH_PASS 비어있으면(로컬 개발) 인증 없이 통과."""
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    client = TestClient(app_module.app)
    r = client.get("/api/reference")
    assert r.status_code == 200


def test_unauthenticated_api_returns_401(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.get("/api/reference")
    assert r.status_code == 401


def test_unauthenticated_page_redirects_to_login(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert r.headers["location"] == "/login"


def test_login_wrong_password_redirects_with_error(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.post("/api/login", data={"user": "admin", "pass": "wrong"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login?e=1"


def test_login_correct_password_sets_cookie_and_grants_access(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.post("/api/login", data={"user": "admin", "pass": "secret123"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert "dash_auth" in r.cookies
    r2 = client.get("/api/reference")
    assert r2.status_code == 200
