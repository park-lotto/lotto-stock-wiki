"""/api/collect 의 category 쿼리 파라미터가 collect(categories=[...])로 전달되는지 검증.

test_app_tiktok_guard.py 의 클라이언트/관리자 통과 패턴을 그대로 재사용한다:
- appmod.DB_PATH 를 tmp DB로 교체
- appmod.collect 를 kwargs 기록용 fake로 교체(app.py가 collect를 모듈로 import함)
- 관리자 게이트는 tiktok 가드 테스트와 동일하게 별도 인증 없이 통과.
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod


def _client(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    recorded = {}

    def fake_collect(platform="instagram", categories=None, limit_channels=None, on_progress=None):
        recorded["platform"] = platform
        recorded["categories"] = categories
        recorded["limit_channels"] = limit_channels
        return []

    monkeypatch.setattr(appmod, "collect", fake_collect)
    return TestClient(appmod.app), recorded


def test_collect_category_maps_to_categories_list(tmp_path, monkeypatch):
    c, recorded = _client(tmp_path, monkeypatch)
    r = c.post("/api/collect?platform=youtube&category=혼합형")
    assert r.status_code == 200
    assert recorded["categories"] == ["혼합형"]


def test_collect_without_category_passes_none(tmp_path, monkeypatch):
    c, recorded = _client(tmp_path, monkeypatch)
    r = c.post("/api/collect?platform=youtube")
    assert r.status_code == 200
    assert recorded["categories"] is None
