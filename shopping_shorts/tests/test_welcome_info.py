# 가입 마무리(이름·전화) 받기 — 2026-08-24
# 구글 로그인 가입은 이메일만 들어와 관리자 고객표의 이름·전화가 통째로 비어 있었다(실측 179명).
# 새 가입자에게 한 번 물어보되, ★기존 고객은 절대 안 붙잡는다(welcome_due 기본 0).
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
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
    return {"dash_auth": appmod._sign_session(cid, exp)}


# ── store: 구글 가입은 마무리 대상, 다 채우면 해제 ──
def test_google_signup_is_flagged_and_clears(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid, created = s.get_or_create_by_google("sub-1", "x@y.com", return_created=True)
    c = s.get_customer(cid)
    assert created and c["welcome_due"] is True                # 이름·전화를 못 받았다
    assert not c["name"] and not c["phone"]
    s.update_customer_info(cid, "홍길동", "010-1234-5678")     # 관리자 수정과 같은 경로
    s.clear_welcome_due(cid)
    c = s.get_customer(cid)
    assert c["name"] == "홍길동" and c["phone"] == "010-1234-5678"
    assert c["welcome_due"] is False                           # 두 번 묻지 않는다


# ★가장 중요한 회귀 방어: 기존 고객이 갑자기 입력화면에 갇히면 안 된다.
def test_existing_customer_is_never_asked(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    old = s.create_customer("olduser", "pw12", approved=True)  # welcome_due 기본 0
    assert s.get_customer(old)["welcome_due"] is False
    assert appmod._needs_welcome(old) is False                 # 이름·전화가 비어도 안 붙잡는다
    cl = TestClient(appmod.app, follow_redirects=False)
    r = cl.get("/", cookies=_cookie(old))
    assert r.headers.get("location") != "/welcome"


def test_owner_is_never_asked(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert appmod._needs_welcome(0) is False                   # 사장님 계정


# ── 흐름: 구글 신규가입자는 이름·전화를 내야 들어간다 ──
def test_new_google_user_is_routed_to_welcome_and_can_submit(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid, _ = s.get_or_create_by_google("sub-A", "theblackart001@gmail.com", return_created=True)
    cl = TestClient(appmod.app, follow_redirects=False)
    ck = _cookie(cid)

    r = cl.get("/", cookies=ck)                                # 홈 → 마무리 화면으로
    assert r.status_code == 303 and r.headers["location"] == "/welcome"

    r = cl.get("/welcome", cookies=ck)                         # ★대기실이 아니라 입력칸이 떠야 한다
    assert r.status_code == 200
    assert "name=name" in r.text and "name=phone" in r.text
    assert "승인 대기중" not in r.text

    r = cl.get("/api/produce/x", cookies=ck)                   # API는 403 + level=welcome
    assert r.status_code == 403 and r.json()["level"] == "welcome"

    r = cl.post("/api/welcome", data={"name": "홍길동", "phone": "010-1234-5678"}, cookies=ck)
    assert r.status_code == 303 and r.headers["location"] == "/"
    c = s.get_customer(cid)
    assert c["name"] == "홍길동" and c["phone"] == "010-1234-5678"

    r = cl.get("/", cookies=ck)                                # 더는 안 붙잡는다
    assert r.headers.get("location") != "/welcome"


def test_welcome_rejects_blank_name_and_bad_phone(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid, _ = s.get_or_create_by_google("sub-B", "b@y.com", return_created=True)
    cl = TestClient(appmod.app, follow_redirects=False)
    ck = _cookie(cid)
    for data in ({"name": "", "phone": "010-1234-5678"},       # 이름 없음
                 {"name": "홍길동", "phone": ""},               # 전화 없음
                 {"name": "홍길동", "phone": "123"}):           # 전화 형식 이상
        r = cl.post("/api/welcome", data=data, cookies=ck)
        assert "welcome?e=" in r.headers.get("location", "")
    assert s.get_customer(cid)["welcome_due"] is True          # 아직 안 냈으니 계속 물어본다


# ── 아이디 가입 폼도 이름·전화를 받는다 ──
def test_id_signup_requires_name_and_phone(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cl = TestClient(appmod.app, follow_redirects=False)
    hdr = {"content-type": "application/x-www-form-urlencoded"}

    cl.post("/api/signup", content="user=blank1&pass=pw12&name=&phone=010-1111-2222", headers=hdr)
    assert s.verify_customer("blank1", "pw12") is None          # 이름 없이는 계정이 안 생긴다
    cl.post("/api/signup", content="user=blank2&pass=pw12&name=%ED%99%8D&phone=", headers=hdr)
    assert s.verify_customer("blank2", "pw12") is None          # 전화 없이도 안 생긴다

    cl.post("/api/signup",
            content="user=good1&pass=pw12&name=%ED%99%8D&phone=010-1111-2222", headers=hdr)
    cid = s.verify_customer("good1", "pw12")
    assert cid is not None
    c = s.get_customer(cid)
    assert c["name"] == "홍" and c["phone"] == "010-1111-2222"
    assert c["welcome_due"] is False                            # 다 냈으니 다시 안 묻는다
