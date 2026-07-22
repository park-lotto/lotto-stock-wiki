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
    assert appmod._ranking_only_blocked("/api/reference", "GET") is False   # 조회 무료
    assert appmod._ranking_only_blocked("/", "GET") is False
    assert appmod._ranking_only_blocked("/api/me", "GET") is False
    assert appmod._ranking_only_blocked("/account", "GET") is False   # 무료 등급도 자기 계정 열람
    assert appmod._ranking_only_blocked("/pricing", "GET") is False   # 요금 페이지 공개
    assert appmod._ranking_only_blocked("/api/thumb", "GET") is False
    assert appmod._ranking_only_blocked("/static/app.js", "GET") is False
    assert appmod._ranking_only_blocked("/api/login", "POST") is False      # 로그인 폼=무료
    # 차단돼야 하는 것들
    assert appmod._ranking_only_blocked("/api/reference", "POST") is True    # 같은 경로여도 POST=차단
    assert appmod._ranking_only_blocked("/api/reference/register", "GET") is True  # 등록=차단
    assert appmod._ranking_only_blocked("/api/collect", "POST") is True      # 수집=차단
    assert appmod._ranking_only_blocked("/api/lens/search", "POST") is True
    assert appmod._ranking_only_blocked("/api/mix/basket", "GET") is True


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

def test_anonymous_root_serves_landing(tmp_path, monkeypatch):
    """비로그인 방문자의 GET / 는 로그인 리다이렉트가 아니라 공개 대문(랜딩)을 200으로 준다."""
    _setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app)  # 쿠키 없음 = 비로그인
    r = c.get("/")
    assert r.status_code == 200
    assert appmod._BRAND["name"] in r.text
    assert "무료로 시작하기" in r.text and "/login" in r.text


def test_anonymous_protected_page_still_redirects_to_login(tmp_path, monkeypatch):
    """대문은 오직 / 만 — 다른 비로그인 HTML 경로는 여전히 /login 으로 보낸다."""
    _setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app, follow_redirects=False)
    r = c.get("/produce.html")
    assert r.status_code in (302, 303, 307)
    assert "/login" in r.headers.get("location", "")


def test_anonymous_pricing_is_public(tmp_path, monkeypatch):
    """비로그인 방문자도 요금·이용권 페이지(/pricing)를 200으로 본다(로그인 리다이렉트 아님)."""
    _setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app)  # 쿠키 없음 = 비로그인
    r = c.get("/pricing")
    assert r.status_code == 200
    assert "이용권" in r.text


def test_pending_gate_blocks_everything(tmp_path, monkeypatch):
    """미승인(pending) 세션은 API=403, 화면=대기실 HTML, /logout만 통과."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pend", "pw12", approved=False)
    with s._conn() as conn:                      # 체험창 만료 강제 → 진짜 pending 상태로 검증
        conn.execute("UPDATE customers SET trial_ends_at=NULL WHERE id=?", (cid,))
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    # 보호 API → 403 pending
    r_api = c.get("/api/reference/register", follow_redirects=False)
    assert r_api.status_code == 403 and r_api.json().get("level") == "pending"
    # 일반 화면 → 대기실 HTML(로그인/랜딩 아님)
    r_home = c.get("/", follow_redirects=False)
    assert r_home.status_code == 200 and "승인" in r_home.text
    # 브랜드명은 라이브와 통일(_fill_brand 통과) — 옛 이름 '숏템탑스' 잔존 금지
    assert appmod._BRAND["name"] in r_home.text
    assert "숏템탑스" not in r_home.text
    # 로그아웃은 통과 — POST가 실제 로그아웃(303), GET은 확인화면(200)
    r_out = c.post("/logout", follow_redirects=False)
    assert r_out.status_code in (302, 303)


def test_logout_get_does_not_clear_session(tmp_path, monkeypatch):
    """CSRF 방어: GET /logout은 세션을 지우지 않는다(<img src=/logout>로 강제 로그아웃 불가).
    대신 로그아웃 확인 화면(POST 버튼)을 200으로 보여준다."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)}, follow_redirects=False)
    r = c.get("/logout")
    # 쿠키를 삭제하는 set-cookie가 없어야 한다(=세션 유지)
    sc = r.headers.get("set-cookie", "")
    assert "dash_auth=;" not in sc and "dash_auth=\"\"" not in sc
    # 확인 화면이어야 한다(리다이렉트로 즉시 로그아웃 아님)
    assert r.status_code == 200
    assert "로그아웃" in r.text


def test_logout_post_clears_session(tmp_path, monkeypatch):
    """POST /logout만 실제 로그아웃(쿠키 삭제 후 /login)."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u2", "pw12")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)}, follow_redirects=False)
    r = c.post("/logout")
    assert r.status_code in (302, 303)
    assert "/login" in r.headers.get("location", "")
    sc = r.headers.get("set-cookie", "")
    assert "dash_auth=" in sc  # 삭제용 set-cookie 존재


def test_pending_can_logout_via_post(tmp_path, monkeypatch):
    """승인대기 유저도 POST /logout으로 탈출 가능(게이트 통과)."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pend", "pw12", approved=False)
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)}, follow_redirects=False)
    r = c.post("/logout")
    assert r.status_code in (302, 303)
    assert "/login" in r.headers.get("location", "")


def test_grab_blocks_pending(tmp_path, monkeypatch):
    """미승인(pending) 계정은 /api/grab 담기 불가 — _AUTH_ALLOW 우회 경로 구멍 막기.
    /api/grab은 200 HTML 팝업이라 상태코드로 구분 안 됨 → 본문 문구로 차단 확인."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pend", "pw12", approved=False)
    with s._conn() as conn:                      # 체험창 만료 강제 → 진짜 pending 상태로 검증
        conn.execute("UPDATE customers SET trial_ends_at=NULL WHERE id=?", (cid,))
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = c.get("/api/grab?url=https://www.youtube.com/watch?v=x&title=t")
    # 대기중은 담기 성공 팝업이 아니라 차단 안내여야 한다
    assert "담겼어요" not in r.text
    assert "승인" in r.text or "대기" in r.text


def test_grab_blocks_ranking_only(tmp_path, monkeypatch):
    """체험만료(ranking_only)도 여전히 /api/grab 차단(회귀 확인)."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("free1", "pw12")
    s.set_plan(cid, "free", full_access_until=0)   # 체험 만료 → ranking_only
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = c.get("/api/grab?url=https://www.youtube.com/watch?v=x&title=t")
    assert "담겼어요" not in r.text
    assert "유료" in r.text


# ── 관리자(cid0) 전용 운영버튼(2026-07-22) — 수집·전수조사·레퍼런스등록 ──
def test_admin_only_endpoints_block_pro_user(tmp_path, monkeypatch):
    """수집·전수조사·레퍼런스등록은 관리자 전용 — pro 구독자(full등급, 비관리자)도 403.
    화면 숨김만으론 pro가 API를 직접 호출할 수 있어 백엔드도 막았다는 증거."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pro9", "pw12")
    s.set_plan(cid, "pro")                     # full 등급이지만 cid≠0 → 관리자 아님
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    # 403(관리자 전용)이지 402(유료)가 아니다 — pro는 유료게이트는 통과하나 관리자 가드에 막힌다
    assert c.post("/api/collect?platform=instagram").status_code == 403
    assert c.post("/api/census").status_code == 403
    assert c.post("/api/reference/register",
                  params={"url": "https://instagram.com/x"}).status_code == 403


def test_discover_run_admin_only_feed_open(tmp_path, monkeypatch):
    """발굴 실행(업데이트·키워드검색)은 관리자 전용(2026-07-23) — 회당 Apify run
    수십 개가 도는 유료 크롤이라 pro도 403. 결과 피드 보기는 전 회원 공유(200)."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pro8", "pw12")
    s.set_plan(cid, "pro")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/discover/update").status_code == 403
    assert c.get("/api/discover?keyword=주방템").status_code == 403
    assert c.get("/api/discover/feed").status_code == 200


def test_admin_can_register_reference(tmp_path, monkeypatch):
    """관리자(cid0)는 레퍼런스 등록 가능 — 가드가 관리자를 막지 않는다(403 아님)."""
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(appmod, "load_channels", lambda: [])   # 엑셀 없이도 동작
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})   # cid0 = 사장님
    r = c.post("/api/reference/register",
               params={"url": "https://instagram.com/adminpick"})
    assert r.status_code == 200 and r.json()["ok"] is True
