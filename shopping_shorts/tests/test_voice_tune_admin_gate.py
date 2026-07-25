"""작업대(발음교정 튜닝 워크벤치)는 관리자(customer_id==0) 전용(2026-07-22).

인증 우회 패턴은 test_pron_api.py를 그대로 따른다: _AUTH_ON=True로 켜고
_sign_session(cid, ...)으로 서명한 dash_auth 쿠키를 세션으로 쓴다
(request.state.customer_id는 _auth_guard 미들웨어가 이 쿠키를 검증해 채운다).
기본 테스트 환경(_AUTH_ON=False)에서는 미들웨어가 모든 요청에 customer_id=0(관리자)를
강제 주입하므로, "비관리자가 막힌다"를 실제로 검증하려면 _AUTH_ON=True로 켜고 진짜
비관리자(customer_id != 0) 계정을 만들어야 한다 — 그렇지 않으면 전원이 관리자라 테스트가
가짜로 통과한다.
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


def test_non_admin_blocked_from_voice_tune_page(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = other.get("/voice_tune", follow_redirects=False)
    assert r.status_code in (403, 401, 302)
    r2 = other.get("/voice_tune.html", follow_redirects=False)
    assert r2.status_code in (403, 401, 302)


def test_admin_can_reach_voice_tune_page(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.get("/voice_tune", follow_redirects=False)
    assert r.status_code == 200
    r2 = owner.get("/voice_tune.html", follow_redirects=False)
    assert r2.status_code == 200


def test_non_admin_blocked_from_voice_tune_api(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert other.get("/api/voice-tune/corpus").status_code == 403
    assert other.post("/api/voice-tune/preview", json={"text": "a"}).status_code == 403
    assert other.post("/api/voice-tune/synth", json={"text": "a"}).status_code == 403
    assert other.get("/api/voice-tune/profile/x").status_code == 403
    assert other.post("/api/voice-tune/profile/x", json={"profile": {}}).status_code == 403


def test_admin_can_reach_voice_tune_api(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.get("/api/voice-tune/corpus")
    assert r.status_code == 200
    r2 = owner.get("/api/voice-tune/profile/x")
    assert r2.status_code == 200


def test_non_admin_blocked_from_pron_api(tmp_path, monkeypatch):
    # /api/pron/global은 이미 관리자 게이트가 있다(test_pron_api.py). 여기선 회귀만 재확인.
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert other.get("/api/pron/global").status_code == 403
