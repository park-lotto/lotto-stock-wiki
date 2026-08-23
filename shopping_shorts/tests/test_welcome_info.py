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


# 브라우저가 '문서를 여는' 요청에 붙이는 헤더. 가입 마무리 화면은 이 요청만 붙잡는다
# (API·이미지·fetch를 막으면 이미 열려 있던 화면이 갑자기 깨진다).
# 실측: 크롬은 페이지 이동에 Sec-Fetch-Mode: navigate를 보낸다. TestClient는 안 보내므로
# 여기서 직접 붙여야 실제와 같은 조건이 된다.
_NAV = {"sec-fetch-mode": "navigate", "accept": "text/html"}


# ── store: 구글 가입은 마무리 대상, 다 채우면 해제 ──
def test_google_signup_is_flagged_and_clears(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid, created = s.get_or_create_by_google("sub-1", "x@y.com", return_created=True)
    c = s.get_customer(cid)
    assert created and c["welcome_due"] is True                # 이름·전화를 못 받았다
    assert not c["name"] and not c["phone"]
    s.update_customer_info(cid, "홍길동", "010-1234-5678",
                           gender="남성", age_band="30대")        # 관리자 수정과 같은 경로
    s.clear_welcome_due(cid)
    c = s.get_customer(cid)
    assert c["name"] == "홍길동" and c["phone"] == "010-1234-5678"
    assert c["gender"] == "남성" and c["age_band"] == "30대"
    assert c["welcome_due"] is False                           # 두 번 묻지 않는다


# ★2026-08-24 사장님 결정: 기존 고객도 다음 접속 때 한 번 받는다(백필).
#   판정은 welcome_due 플래그가 아니라 '실제로 비었는가'로 한다.
def test_existing_customer_with_blanks_is_asked(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    old = s.create_customer("olduser", "pw12", approved=True)  # 이름·전화·성별·연령 전부 없음
    assert s.get_customer(old)["welcome_due"] is False         # 플래그는 꺼져 있지만
    assert appmod._needs_welcome(old) is True                  # 비었으니 물어본다
    cl = TestClient(appmod.app, follow_redirects=False)
    r = cl.get("/", cookies=_cookie(old), headers=_NAV)
    assert r.headers["location"] == "/welcome"


# 이름·전화는 있는데 성별·연령만 빈 고객도 물어본다(사장님이 고른 백필 범위).
def test_partially_filled_customer_is_asked(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("halfuser", "pw12", approved=True,
                            name="김철수", phone="010-1234-5678")
    assert appmod._welcome_missing(s.get_customer(cid)) == ["gender", "age_band"]
    assert appmod._needs_welcome(cid) is True
    # 화면에 이미 아는 값(이름·전화)이 채워져 나와야 한다 — 다시 치게 하면 안 된다
    cl = TestClient(appmod.app, follow_redirects=False)
    r = cl.get("/welcome", cookies=_cookie(cid), headers=_NAV)
    assert 'value="김철수"' in r.text and 'value="010-1234-5678"' in r.text


# 다 채운 고객은 두 번 다시 안 붙잡힌다(무한 리다이렉트 방지).
def test_fully_filled_customer_is_never_asked(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("fulluser", "pw12", approved=True, name="김철수",
                            phone="010-1234-5678", gender="남성", age_band="30대")
    assert appmod._needs_welcome(cid) is False
    cl = TestClient(appmod.app, follow_redirects=False)
    r = cl.get("/", cookies=_cookie(cid), headers=_NAV)
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

    r = cl.get("/", cookies=ck, headers=_NAV)                                # 홈 → 마무리 화면으로
    assert r.status_code == 303 and r.headers["location"] == "/welcome"

    r = cl.get("/welcome", cookies=ck, headers=_NAV)                         # ★대기실이 아니라 입력칸이 떠야 한다
    assert r.status_code == 200
    assert "name=name" in r.text and "name=phone" in r.text
    assert "name=gender" in r.text and "name=age_band" in r.text
    for opt in ("남성", "여성", "20대", "30대", "40대", "50대", "기타"):
        assert opt in r.text                                   # 선택지가 다 그려져야 한다
    assert "승인 대기중" not in r.text

    r = cl.get("/api/produce/x", cookies=ck)                   # API는 접근권한 게이트가 처리
    assert r.status_code == 403 and r.json()["level"] == "pending"

    r = cl.post("/api/welcome",
                data={"name": "홍길동", "phone": "010-1234-5678",
                      "gender": "남성", "age_band": "30대"}, cookies=ck)
    assert r.status_code == 303 and r.headers["location"] == "/"
    c = s.get_customer(cid)
    assert c["name"] == "홍길동" and c["phone"] == "010-1234-5678"
    assert c["gender"] == "남성" and c["age_band"] == "30대"

    r = cl.get("/", cookies=ck, headers=_NAV)                                # 더는 안 붙잡는다
    assert r.headers.get("location") != "/welcome"


def test_welcome_rejects_blank_name_and_bad_phone(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid, _ = s.get_or_create_by_google("sub-B", "b@y.com", return_created=True)
    cl = TestClient(appmod.app, follow_redirects=False)
    ck = _cookie(cid)
    ok = {"name": "홍길동", "phone": "010-1234-5678", "gender": "남성", "age_band": "30대"}
    for bad in ({**ok, "name": ""},                            # 이름 없음
                {**ok, "phone": ""},                           # 전화 없음
                {**ok, "phone": "123"},                        # 전화 형식 이상
                {**ok, "gender": ""},                          # 성별 안 고름
                {**ok, "age_band": ""},                        # 연령대 안 고름
                {**ok, "gender": "외계인"},                     # ★목록에 없는 값(curl 우회)
                {**ok, "age_band": "999대"}):                   # ★목록에 없는 값
        r = cl.post("/api/welcome", data=bad, cookies=ck)
        assert "welcome?e=" in r.headers.get("location", ""), bad
    assert appmod._needs_welcome(cid) is True                  # 아직 안 냈으니 계속 물어본다


# ── 아이디 가입 폼도 이름·전화를 받는다 ──
def test_id_signup_requires_name_and_phone(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cl = TestClient(appmod.app, follow_redirects=False)
    hdr = {"content-type": "application/x-www-form-urlencoded"}

    G, A = "%EB%82%A8%EC%84%B1", "30%EB%8C%80"                  # 남성 / 30대
    cl.post("/api/signup",
            content=f"user=blank1&pass=pw12&name=&phone=010-1111-2222&gender={G}&age_band={A}",
            headers=hdr)
    assert s.verify_customer("blank1", "pw12") is None           # 이름 없이는 계정이 안 생긴다
    cl.post("/api/signup",
            content=f"user=blank2&pass=pw12&name=%ED%99%8D&phone=&gender={G}&age_band={A}",
            headers=hdr)
    assert s.verify_customer("blank2", "pw12") is None           # 전화 없이도 안 생긴다
    cl.post("/api/signup",
            content="user=blank3&pass=pw12&name=%ED%99%8D&phone=010-1111-2222", headers=hdr)
    assert s.verify_customer("blank3", "pw12") is None           # 성별·연령 없이도 안 생긴다

    cl.post("/api/signup",
            content=f"user=good1&pass=pw12&name=%ED%99%8D&phone=010-1111-2222"
                    f"&gender={G}&age_band={A}", headers=hdr)
    cid = s.verify_customer("good1", "pw12")
    assert cid is not None
    c = s.get_customer(cid)
    assert c["name"] == "홍" and c["phone"] == "010-1111-2222"
    assert c["gender"] == "남성" and c["age_band"] == "30대"
    # ★가입폼에서 다 받았으니 /welcome으로 또 끌려가면 안 된다(두 번 묻는 꼴)
    assert appmod._needs_welcome(cid) is False
