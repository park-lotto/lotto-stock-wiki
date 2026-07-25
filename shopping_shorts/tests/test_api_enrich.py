"""POST /api/enrich — 유튜브 자동조회+캐시, 비유튜브 관리자 게이트 (2026-07-22)."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import shopping_shorts.app as app_mod


def _client(monkeypatch, tmp_path):
    """DB_PATH를 임시 DB로 돌려 테스트끼리 격리(기존 test_paywall_admin.py와 동일 패턴).
    인증은 기본 꺼짐(_AUTH_ON=False) → 모든 요청이 customer_id=0(관리자)."""
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(app_mod.app)


def test_enrich_youtube_auto_then_cache(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_enrich(url):
        calls["n"] += 1
        return {"platform": "youtube", "channel_name": "채널", "subscribers": 5,
                "views": 9, "likes": 1, "comment_count": 2, "upload_date": "2026-07-01",
                "caption": "cap", "top_comments": [{"author": "A", "text": "c", "likes": 0}],
                "channel_url": "https://youtube.com/@c"}

    monkeypatch.setattr(app_mod, "enrich_youtube", fake_enrich)
    c = _client(monkeypatch, tmp_path)
    r1 = c.post("/api/enrich", json={"url": "https://youtu.be/abc123DEF45", "platform": "youtube"})
    assert r1.json()["channel_name"] == "채널" and r1.json()["status"] == "ok"
    r2 = c.post("/api/enrich", json={"url": "https://youtu.be/abc123DEF45", "platform": "youtube"})
    assert r2.json()["channel_name"] == "채널"
    assert calls["n"] == 1  # 두 번째는 캐시 히트(재조회 안 함)


def test_enrich_youtube_no_data_caches_no_refetch(monkeypatch, tmp_path):
    """enrich_youtube가 None(영상 없음/삭제됨)이면 no_data를 캐시하고 재조회 안 함."""
    calls = {"n": 0}

    def fake_enrich(url):
        calls["n"] += 1
        return None

    monkeypatch.setattr(app_mod, "enrich_youtube", fake_enrich)
    c = _client(monkeypatch, tmp_path)
    r1 = c.post("/api/enrich", json={"url": "https://youtu.be/deadDEADdea", "platform": "youtube"})
    assert r1.json()["status"] == "no_data"
    r2 = c.post("/api/enrich", json={"url": "https://youtu.be/deadDEADdea", "platform": "youtube"})
    assert r2.json()["status"] == "no_data"
    assert calls["n"] == 1  # no_data도 캐시되어 두 번째는 재조회 안 함


def test_enrich_youtube_quota_not_cached(monkeypatch, tmp_path):
    """쿼터소진은 캐시하지 않는다 — 다음 호출이 다른 키로 다시 시도할 수 있어야 함."""
    calls = {"n": 0}

    def fake_enrich(url):
        calls["n"] += 1
        return {"status": "quota"}

    monkeypatch.setattr(app_mod, "enrich_youtube", fake_enrich)
    c = _client(monkeypatch, tmp_path)
    r1 = c.post("/api/enrich", json={"url": "https://youtu.be/quotaquota12", "platform": "youtube"})
    assert r1.json()["status"] == "quota"
    r2 = c.post("/api/enrich", json={"url": "https://youtu.be/quotaquota12", "platform": "youtube"})
    assert r2.json()["status"] == "quota"
    assert calls["n"] == 2  # 캐시 안 됐으므로 매번 재조회 시도


def test_enrich_empty_url_no_data(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/enrich", json={"url": "", "platform": "youtube"})
    assert r.json()["status"] == "no_data"


def test_enrich_non_youtube_needs_manual(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/enrich", json={"url": "https://www.tiktok.com/@x/video/1", "platform": "tiktok"})
    assert r.json()["status"] == "needs_manual"


def test_enrich_non_youtube_force_admin_ok_stub(monkeypatch, tmp_path):
    """인증 꺼짐(기본) → customer_id=0=관리자 취급이라 force도 403 없이 통과,
    Apify 미구현 스텁이라 no_data를 반환한다."""
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/enrich", json={"url": "https://www.tiktok.com/@x/video/1",
                                     "platform": "tiktok", "force": True})
    assert r.status_code == 200
    assert r.json()["status"] == "no_data"


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return app_mod._sign_session(cid, exp)


def test_enrich_non_youtube_force_requires_admin(monkeypatch, tmp_path):
    """비관리자(customer_id!=0)가 force로 비유튜브 실조회 → 403.

    인증 OFF면 전원 admin(customer_id=0)이 되어 이 테스트가 무의미해지므로,
    test_paywall_admin.py의 관리자/비관리자 세션 세팅(_AUTH_ON=True + DASH_SECRET +
    _sign_session 쿠키)을 그대로 빌려 customer_id!=0인 진짜 비관리자 요청을 만든다."""
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(app_mod, "_AUTH_ON", True)
    monkeypatch.setattr(app_mod, "DASH_SECRET", "test-secret-xyz")
    s = app_mod.Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u1", "pw12")   # 일반 고객(체험중) — customer_id != 0
    non_admin = TestClient(app_mod.app, cookies={"dash_auth": _cookie(cid)})
    r = non_admin.post("/api/enrich", json={"url": "https://www.tiktok.com/@x/video/1",
                                             "platform": "tiktok", "force": True})
    assert r.status_code == 403


def test_enrich_non_youtube_force_admin_passes_gate(monkeypatch, tmp_path):
    """관리자(customer_id=0)는 같은 인증-켜짐 환경에서도 403 없이 통과(스텁이라 no_data)."""
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(app_mod, "_AUTH_ON", True)
    monkeypatch.setattr(app_mod, "DASH_SECRET", "test-secret-xyz")
    app_mod.Store(str(tmp_path / "t.db"))
    owner = TestClient(app_mod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/enrich", json={"url": "https://www.tiktok.com/@x/video/1",
                                         "platform": "tiktok", "force": True})
    assert r.status_code == 200
    assert r.json()["status"] == "no_data"
