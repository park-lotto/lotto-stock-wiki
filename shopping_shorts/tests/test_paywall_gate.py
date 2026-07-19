"""유료게이트 Task2 — deny-by-default API 게이트 (2026-07-19)."""
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


def test_ranking_only_blocked_helper():
    assert appmod._ranking_only_blocked("/api/reference") is False   # 조회 무료
    assert appmod._ranking_only_blocked("/") is False
    assert appmod._ranking_only_blocked("/api/me") is False
    assert appmod._ranking_only_blocked("/api/thumb") is False
    assert appmod._ranking_only_blocked("/api/reference/register") is True   # 등록=차단
    assert appmod._ranking_only_blocked("/api/collect") is True              # 수집=차단
    assert appmod._ranking_only_blocked("/api/lens/search") is True
    assert appmod._ranking_only_blocked("/api/mix/basket") is True


def test_free_user_blocked_from_paid_but_ranking_ok(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("free1", "pw12")
    s.set_plan(cid, "free", full_access_until=0)     # 체험 만료 → ranking_only
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/reference?platform=instagram").status_code == 200   # 랭킹 조회 OK
    assert c.get("/api/mix/basket").status_code == 402                     # 유료 차단
    assert c.post("/api/collect?platform=instagram").status_code == 402    # 수집 차단


def test_pro_user_not_blocked(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pro1", "pw12")
    s.set_plan(cid, "pro")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/mix/basket").status_code != 402   # pro는 안 막힘


def test_trial_user_not_blocked(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("trial1", "pw12")   # 가입시 체험 자동시작 → full
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/mix/basket").status_code != 402
