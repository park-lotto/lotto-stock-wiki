import pytest
from fastapi.testclient import TestClient
from shopping_shorts.app import app


@pytest.fixture
def client():
    return TestClient(app)


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


def test_find_analyze_downloads_extracts_analyzes_and_saves(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store
    from shopping_shorts.config import DB_PATH

    # 마지막 수집 결과에 분석 대상 아이템을 하나 심어둔다
    store = Store(DB_PATH)
    store.save_last_run([{
        "shortcode": "sc1", "video_url": "https://example.com/v.mp4",
        "caption": "여름 바닥 청소", "thumbnail": "t.jpg",
    }], "2026-07-09T00:00:00Z")

    monkeypatch.setattr(app_module, "download_video", lambda url, dest: tmp_path / "v.mp4")
    (tmp_path / "v.mp4").write_bytes(b"fake")
    monkeypatch.setattr(app_module, "extract_frames",
                         lambda video_path, dest, max_frames: [tmp_path / "frame_01.jpg"])
    (tmp_path / "frame_01.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(app_module, "analyze_video", lambda path, caption: {
        "keywords": {"ko": ["바닥 청소"], "en": ["floor cleaner"], "zh": ["地板清洁"]},
        "category": "생활용품/홈케어",
    })

    r = client.post("/api/find/analyze", params={"shortcode": "sc1"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["keywords"]["ko"] == ["바닥 청소"]
    assert "youtube" in d["search_links"]
    assert len(d["frame_urls"]) == 1

    # 저장도 됐는지
    saved = store.get_source_analysis("sc1")
    assert saved["keywords"]["ko"] == ["바닥 청소"]


def test_find_analyze_unknown_shortcode_404(client):
    r = client.post("/api/find/analyze", params={"shortcode": "nope"})
    assert r.status_code == 404
