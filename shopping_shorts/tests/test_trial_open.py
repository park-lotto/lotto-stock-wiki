"""체험판 개방(2026-08-20) — 랭킹·즐겨찾기·렌즈는 열고 제작소 API는 계속 막는다."""
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


def test_favorites_and_lens_open_for_ranking_only():
    """즐겨찾기 담기·목록과 과금검사 있는 렌즈 2개는 열린다."""
    assert appmod._ranking_only_blocked("/api/mix/basket", "GET") is False
    assert appmod._ranking_only_blocked("/api/mix/basket/toggle", "POST") is False
    assert appmod._ranking_only_blocked("/collection", "GET") is False
    assert appmod._ranking_only_blocked("/api/lens/search", "POST") is False
    assert appmod._ranking_only_blocked("/api/lens/trace_url", "POST") is False


def test_unmetered_lens_and_produce_api_still_blocked():
    """★과금검사 없는 렌즈는 계속 막는다 — prefix로 열면 Apify 유료가 샌다."""
    assert appmod._ranking_only_blocked("/api/lens/kw/search", "POST") is True
    assert appmod._ranking_only_blocked("/api/lens/cn/search", "POST") is True
    assert appmod._ranking_only_blocked("/api/lens/yt", "POST") is True
    assert appmod._ranking_only_blocked("/api/lens/single", "GET") is True
    # 제작소 API는 HTML을 열어도 계속 막힌다(과금 기능 유출 방지)
    assert appmod._ranking_only_blocked("/api/produce/mix/clean", "POST") is True
    assert appmod._ranking_only_blocked("/api/produce/script/mix", "POST") is True
    # 담기 파생 경로도 열지 않았다
    assert appmod._ranking_only_blocked("/api/mix/basket/reprobe", "POST") is True


def test_free_user_can_toggle_basket(tmp_path, monkeypatch):
    """실제 요청으로 담기가 200을 받는다(402가 아니다)."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("trial1", "pw12")
    s.set_plan(cid, "free", full_access_until=0)      # ranking_only
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/mix/basket").status_code == 200
    r = c.post("/api/mix/basket/toggle", json={"shortcode": "ABC123", "url": ""})
    assert r.status_code == 200
    assert r.json()["in"] is True
