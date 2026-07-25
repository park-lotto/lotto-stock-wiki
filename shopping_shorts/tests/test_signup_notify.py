# 새 회원 가입 알림(2026-07-24): 텔레 알림 발송 · pending 폴링 엔드포인트 · 구글 신규여부
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts import notify
from shopping_shorts.store import Store


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    appmod._ACCESS_SEEN.clear()
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


# ── store: pending 목록 ──
def test_pending_customers_only_unapproved_newest_first(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    a = s.create_customer("a", "pw12", approved=False, name="에이")
    s.create_customer("b", "pw12", approved=True)              # 승인됨 → 제외
    c = s.create_customer("c", "pw12", approved=False, name="씨")
    pend = s.pending_customers()
    assert [p["id"] for p in pend] == [c, a]                   # 최근(id DESC) 먼저, 승인자 b 제외
    assert pend[0]["name"] == "씨"


# ── store: 구글 신규여부 플래그 ──
def test_google_return_created_flag(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid, created = s.get_or_create_by_google("sub-1", "x@y.com", return_created=True)
    assert created is True                                     # 첫 로그인 = 신규가입
    cid2, created2 = s.get_or_create_by_google("sub-1", "x@y.com", return_created=True)
    assert cid2 == cid and created2 is False                  # 재로그인 = 신규 아님
    assert s.get_or_create_by_google("sub-1") == cid          # 하위호환(플래그 없으면 cid만)


# ── API: pending 폴링 엔드포인트 ──
def test_admin_pending_endpoint(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    s.create_customer("waiter", "pw12", approved=False, name="대기자", phone="010-1")
    cl = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})   # cid0=사장님
    r = cl.get("/api/admin/pending")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 1 and d["newest"]["name"] == "대기자" and d["newest_id"] > 0


def test_admin_pending_blocks_non_admin(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u", "pw12", approved=True)
    cl = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = cl.get("/api/admin/pending")
    assert r.status_code != 200                                # 비관리자 차단 → 폴러 꺼짐


# ── API: 가입 시 텔레 알림 발송 ──
def test_signup_fires_telegram_notify(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    sent = {}
    monkeypatch.setattr(notify, "send_telegram", lambda text, **k: sent.setdefault("text", text) or True)
    cl = TestClient(appmod.app)
    r = cl.post("/api/signup",
                content="user=hong&pass=pw12&name=홍길동&phone=010-2222",
                headers={"content-type": "application/x-www-form-urlencoded"},
                follow_redirects=False)
    assert r.status_code == 303
    assert "홍길동" in sent.get("text", "") and "새 가입" in sent.get("text", "")
