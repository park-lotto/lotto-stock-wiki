"""PC 등록 게이트 — 1번·2번 PC만, 3번째는 차단 (2026-08-31).

★사장님 지시: "pc를 등록하게 해줘 1번pc 2번pc 다른곳에선 안되게" + "모바일은 상관없고".
★해제는 사장님만(관리자 화면), 3번째는 처음부터 바로 차단 — 둘 다 사장님이 정했다.

여기서 잠그는 계약:
  1. 처음 쓰는 PC 2대가 자동 등록되고, 3번째 PC는 막힌다
  2. 모바일은 몇 대든 안 막힌다(IP·기기 다 무시)
  3. 사장님(admin) 계정은 안 막힌다
  4. 막혀도 /logout은 열려 있다 — 아니면 계정을 바꿀 수조차 없다
  5. 무슨 일이 생겨도 fail-open — 이 기능 고장으로 결제고객이 잠기면 안 된다
"""
import pathlib
import tempfile

import pytest

from shopping_shorts.store import Store

PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
MOB = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E Safari"


@pytest.fixture
def st():
    return Store(str(pathlib.Path(tempfile.mkdtemp()) / "t.db"))


def test_two_pcs_register_then_third_is_blocked(st):
    """★등록은 사람이 누를 때만(device_register). 조회(device_check)는 등록하지 않는다."""
    assert st.device_register(9, "aaa", PC, "1.1.1.1")[:2] == (True, 1)
    assert st.device_register(9, "bbb", PC, "2.2.2.2")[:2] == (True, 2)
    ok, slot, why = st.device_register(9, "ccc", PC, "3.3.3.3")
    assert ok is False and "2대" in why, f"3번째 PC가 안 막혔다({why})"
    assert st.device_check(9, "ccc", PC, "3.3.3.3")[0] is False


def test_check_never_registers(st):
    """★2026-08-31 라이브 사고의 뿌리: 조회가 등록까지 하면, 페이지 하나 열 때 나가는
    동시 요청들이 각각 다른 도장으로 칸을 먹는다(4명 전원 같은 IP였다)."""
    for _ in range(5):
        st.device_check(9, "same-pc-many-requests", PC, "1.1.1.1")
    assert st.device_list(9) == [], "조회만 했는데 등록됐다"


def test_registering_same_pc_twice_uses_one_slot(st):
    """★한 PC가 두 칸을 먹으면 안 된다 — 그게 최일환님이 갇힌 이유였다."""
    st.device_register(9, "aaa", PC, "1.1.1.1")
    ok, slot, why = st.device_register(9, "aaa", PC, "1.1.1.1")
    assert ok and slot == 1 and len(st.device_list(9)) == 1, "같은 PC가 두 칸을 먹었다"


def test_registered_pc_passes_even_when_ip_changes(st):
    """★핵심: IP가 바뀌어도 같은 PC면 통과해야 한다(유동 IP라 매번 바뀐다)."""
    st.device_register(9, "aaa", PC, "1.1.1.1")
    ok, slot, _ = st.device_check(9, "aaa", PC, "77.77.77.77")
    assert ok and slot == 1, "IP가 바뀌었다고 같은 PC를 막았다"


def test_reset_frees_a_slot(st):
    st.device_register(9, "aaa", PC, "1.1.1.1")
    st.device_register(9, "bbb", PC, "2.2.2.2")
    assert st.device_register(9, "ccc", PC, "3.3.3.3")[0] is False
    st.device_reset(9, 2)                       # 사장님이 2번 칸 해제
    ok, slot, _ = st.device_register(9, "ccc", PC, "3.3.3.3")
    assert ok and slot == 2, "해제했는데도 안 들어온다"
    st.device_reset(9)                          # 전부 해제
    assert st.device_list(9) == []


def test_no_device_id_never_blocks(st):
    """도장이 없으면 판단 불가 — 막지 않는다(fail-open)."""
    assert st.device_check(9, "", PC, "1.1.1.1")[0] is True
    assert st.device_check(0, "aaa", PC, "1.1.1.1")[0] is True


def test_list_shows_what_admin_needs(st):
    st.device_register(9, "aaa", PC, "1.1.1.1")
    d = st.device_list(9)[0]
    assert d["slot"] == 1 and d["device_id"] == "aaa"
    assert d["ua"] == PC and d["ip"] == "1.1.1.1"
    assert d["first_seen"] > 0 and d["last_seen"] > 0


def test_counts_for_admin_list(st):
    st.device_register(1, "a", PC, "1.1.1.1")
    st.device_register(1, "b", PC, "1.1.1.2")
    st.device_register(2, "c", PC, "1.1.1.3")
    assert st.device_list_all() == {1: 2, 2: 1}


def test_slot_count_is_defined_in_one_place():
    """★2대라는 숫자가 여러 곳에 박히면 늘릴 때 한 곳만 고쳐져 어긋난다."""
    assert Store.PC_SLOTS == 2


# ── 실제 HTTP 경로 (미들웨어까지 태운다) ──────────────────────────────────────
@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from shopping_shorts import app as app_mod
    return TestClient(app_mod.app), app_mod


def _login(client, app_mod, cid):
    """세션 쿠키를 직접 심는다 — 로그인 화면을 거치지 않고 그 계정으로 요청한다."""
    client.cookies.set("dash_auth", app_mod._sign_session(cid, 2 ** 31))


def test_mobile_is_never_gated(client):
    c, app_mod = client
    r = c.get("/produce.html", headers={"user-agent": MOB})
    assert r.status_code != 403, "모바일이 막혔다 — 사장님: 모바일은 상관없다"


def test_stamp_never_hijacks_a_redirect(client):
    """★도장 때문에 화면 이동을 가로채면 안 된다(2026-08-31 게이트가 잡은 사고).

    도장 찍기를 303 리다이렉트로 했더니, 그 응답이 승인·유료·가입마무리 게이트보다
    **먼저** 떠서 신규 가입자가 /welcome 대신 /로 튕겼다. 이제는 리다이렉트 없이
    나가는 응답에 쿠키만 얹는다 — 그러니 '같은 URL로 되돌리는 303'은 없어야 한다.
    """
    c, app_mod = client
    r = c.get("/produce.html", headers={"user-agent": PC}, follow_redirects=False)
    loc = r.headers.get("location", "")
    assert not loc.endswith("/produce.html"), f"도장이 화면 이동을 가로챘다({loc})"


def test_stamp_is_written_by_the_middleware_not_a_redirect():
    """★도장을 찍는 코드가 한 곳뿐인지 본다 — 두 군데서 찍으면 칸을 두 개 먹는다."""
    src = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    txt = src.read_text(encoding="utf-8")
    assert txt.count("set_cookie(_DEVICE_COOKIE") == 1, "도장 찍는 곳이 한 곳이 아니다"


def test_logout_stays_open_even_when_blocked(client):
    """★막힌 사람도 로그아웃은 돼야 한다 — 아니면 계정을 바꿀 수조차 없다."""
    c, app_mod = client
    r = c.get("/logout", headers={"user-agent": PC}, follow_redirects=False)
    assert r.status_code != 403


# ── 기존 고객은 소급 적용하지 않는다 (2026-08-31) ─────────────────────────────
def test_gate_applies_only_to_new_signups():
    """★사장님: "지금부터 가입받는사람은 필수". 기존 고객까지 잠그면 잘 쓰던 사람이
    어느 날 갑자기 막힌다 — 실제로 최일환님이 그렇게 갇혔다."""
    from shopping_shorts import app as app_mod
    old = {"created_at": "2026-08-01 10:00:00"}
    new = {"created_at": "2026-09-01 10:00:00"}
    assert app_mod._pc_gate_applies(old) is False, "기존 고객이 소급 적용됐다"
    assert app_mod._pc_gate_applies(new) is True, "신규 가입자가 안 걸린다"
    # 판단이 안 되면 강제하지 않는다(fail-open)
    assert app_mod._pc_gate_applies({}) is False
    assert app_mod._pc_gate_applies(None) is False


def test_gate_cutoff_is_a_single_constant():
    """★기준 시각이 두 곳에 적히면 화면과 서버가 다른 답을 낸다."""
    from shopping_shorts import app as app_mod
    src = pathlib.Path(app_mod.__file__).read_text(encoding="utf-8")
    assert src.count("_PC_GATE_FROM = ") == 1


def test_gate_never_locks_the_registration_path():
    """★교착 금지: '등록하세요'라고 막아놓고 등록 화면까지 막으면 아무것도 못 한다.

    2026-08-31 게이트가 /api/welcome 403을 잡아 발견했다. 마이페이지(/settings)는
    테스트가 못 잡았지만 같은 교착이라 함께 연다.
    """
    from shopping_shorts import app as app_mod
    for path in ("/settings", "/welcome", "/api/welcome", "/logout", "/login",
                 "/api/my/devices", "/api/my/devices/register", "/setup",
                 # ★페이지만 열고 그 데이터 API를 막으면 화면이 통째로 빈다(2026-08-31 실측)
                 "/api/settings/keys", "/api/settings/points", "/api/me",
                 "/api/bug-report/replies"):
        assert app_mod._pc_gate_open_path(path), f"{path}가 막히면 등록할 길이 없다"
    # 정작 막아야 할 길은 열려 있으면 안 된다
    for path in ("/produce.html", "/api/mix/start", "/api/produce/mix/render"):
        assert not app_mod._pc_gate_open_path(path), f"{path}가 통째로 열려 있다"


def test_trial_users_are_not_gated(monkeypatch):
    """★체험판·무료(랭킹만)는 게이트 제외 — 랭킹만 보는 분에게 PC 등록은 과하다.
    실측 2026-08-31: 체험판 고객이 '결제하세요'와 'PC 등록하세요'를 함께 맞았다."""
    from shopping_shorts import app as app_mod

    class _Req:
        headers = {"user-agent": PC}
        cookies = {}
        state = type("S", (), {})()
        url = "http://x/produce.html"
        method = "GET"

    monkeypatch.setattr(app_mod, "access_level", lambda cid, cust=None: "ranking_only")
    assert app_mod._check_pc_device(999, _Req(), "/produce.html") is None


# ── 🖥 골라 해제 (2026-09-15 사장님 "내가 선택해서 지우게") ────────────────────
# 배경: API는 처음부터 slot을 받았는데 관리자 화면이 slot을 안 보내 **전부 해제만**
#   됐다. 2대 상한이라 PC 1대 바꾼 회원에게 전부 해제를 쓰면 멀쩡한 PC까지 재등록
#   (회원이 직접 눌러야 함)시켜야 한다 — 안 쓰는 칸만 빼주는 게 맞다.
def _admin(client, app_mod):
    """사장님(cid 0)으로 로그인 — device_reset은 관리자 전용이다."""
    _login(client, app_mod, 0)


def test_admin_can_release_one_slot_and_keep_the_other(client):
    """★이 테스트가 이 기능의 존재 이유다 — 1대만 빼고 나머지는 살아 있어야 한다."""
    c, app_mod = client
    st = Store(app_mod.DB_PATH)
    st.device_reset(4242)
    st.device_register(4242, "old-pc", PC, "1.1.1.1")
    st.device_register(4242, "using-pc", PC, "2.2.2.2")
    _admin(c, app_mod)

    r = c.post("/api/admin/customer/device_reset",
               json={"customer_id": 4242, "slot": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    # ★응답이 '몇 대 지웠는지'를 말해야 한다 — ok:True 만 주면 화면이 조용한 실패를
    #   "해제했습니다"로 덮는다(실사고 유형: 삭제가 저장출구에서 부활).
    assert body["removed"] == 1 and body["left"] == 1, body
    left = st.device_list(4242)
    assert [d["slot"] for d in left] == [2], "1대만 빼야 하는데 다른 칸까지 지워졌다"
    assert left[0]["device_id"] == "using-pc", "쓰던 PC가 지워졌다"


def test_admin_release_all_when_slot_omitted(client):
    """slot을 안 보내면 전부 해제 — 기존 동작이 그대로 살아 있어야 한다."""
    c, app_mod = client
    st = Store(app_mod.DB_PATH)
    st.device_reset(4243)
    st.device_register(4243, "a", PC, "1.1.1.1")
    st.device_register(4243, "b", PC, "2.2.2.2")
    _admin(c, app_mod)

    body = c.post("/api/admin/customer/device_reset",
                  json={"customer_id": 4243}).json()
    assert body["removed"] == 2 and body["left"] == 0, body
    assert st.device_list(4243) == []


def test_release_refuses_a_slot_that_is_not_registered(client):
    """★없는 칸을 "해제했습니다"라고 하면 안 된다 — 전엔 ok:True 였다."""
    c, app_mod = client
    st = Store(app_mod.DB_PATH)
    st.device_reset(4244)
    st.device_register(4244, "only", PC, "1.1.1.1")     # 1번만 등록
    _admin(c, app_mod)

    r = c.post("/api/admin/customer/device_reset",
               json={"customer_id": 4244, "slot": 2})
    assert r.status_code == 404, r.text
    assert [d["slot"] for d in st.device_list(4244)] == [1], "거부했는데 DB가 바뀌었다"


def test_release_rejects_out_of_range_and_non_numeric_slot(client):
    """slot=99는 조용히 0건 삭제(ok:True)였고, slot='abc'는 int()에서 500이었다."""
    c, app_mod = client
    st = Store(app_mod.DB_PATH)
    st.device_reset(4245)
    st.device_register(4245, "keep", PC, "1.1.1.1")
    _admin(c, app_mod)

    for bad in (99, 0, -1, "abc"):
        r = c.post("/api/admin/customer/device_reset",
                   json={"customer_id": 4245, "slot": bad})
        assert r.status_code == 400, f"slot={bad!r} 를 400으로 막지 않았다({r.status_code})"
    assert [d["slot"] for d in st.device_list(4245)] == [1], "거부했는데 DB가 바뀌었다"


def test_release_needs_admin(tmp_path, monkeypatch):
    """해제는 사장님만 — 회원이 스스로 풀면 돌려쓰기를 막는 의미가 없다.

    ★인증을 켜야 재진다. 꺼져 있으면(DASH_PASS 미설정=로컬 개발) 이 코드베이스는
      전원 admin 취급이라 가드가 없어도 통과하는 **가짜 green**이 된다.
    ★★`monkeypatch.setenv("DASH_PASS", …)`로는 안 켜진다 — _AUTH_ON은 app.py가 처음
      import될 때 한 번만 읽힌다. 기존 관례대로 스위치를 직접 켠다
      (test_bot_api.py·test_admin_customer_mgmt.py 가 같은 패턴).
    """
    from fastapi.testclient import TestClient
    from shopping_shorts import app as app_mod

    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(app_mod, "_AUTH_ON", True)
    st = Store(app_mod.DB_PATH)
    st.device_register(4246, "x", PC, "1.1.1.1")
    c = TestClient(app_mod.app)
    _login(c, app_mod, 4246)                       # 본인 계정으로 시도

    r = c.post("/api/admin/customer/device_reset",
               json={"customer_id": 4246, "slot": 1})
    # 401/403(관리자 아님) 또는 402(유료 게이트)로 막힌다 — 어느 층이 막든 **지워지면
    # 안 된다**가 계약이다. 실측 2026-09-15: 이 계정은 402가 먼저 걸린다.
    assert r.status_code in (401, 402, 403), r.text
    assert len(st.device_list(4246)) == 1, "관리자가 아닌데 지워졌다"

    # ★관리자 가드 자체도 직접 재라 — 위가 402로 막히면 _require_admin은 안 태워진다.
    #   이 함수가 '관리자 아님'을 정하는 한 곳이다.
    assert app_mod._is_admin(4246) is False, "일반 회원이 관리자로 판정된다"
    assert app_mod._is_admin(0) is True, "사장님(0)이 관리자가 아니라고 나온다"


def test_admin_page_sends_the_chosen_slot(_=None):
    """★화면이 slot을 **실제로 보내는지** 잠근다 — API가 받아도 화면이 안 보내면
    '전부 해제'로 되돌아간다(그게 2026-09-15 전까지의 상태였다)."""
    html = (pathlib.Path(__file__).resolve().parents[1]
            / "static" / "admin.html").read_text(encoding="utf-8")
    assert "body.slot = Number(ans)" in html, "고른 번호를 요청에 안 싣는다"
    assert "해제할 PC 번호를 입력하세요" in html, "번호를 고르게 묻지 않는다"
    # 응답을 보고 말해야 한다 — 전엔 실패해도 '해제했습니다'였다
    assert "if(!r || !r.ok)" in html, "응답을 안 보고 성공이라고 말한다"


def test_admin_page_has_no_dead_refresh_call(_=None):
    """★`loadCustomers`는 이 파일에 **없는 함수**다. typeof 방어에 걸려 조용히 아무것도
    안 했고, 그래서 해제·기간설정 후 화면이 갱신되지 않았다(2026-09-15 실측)."""
    html = (pathlib.Path(__file__).resolve().parents[1]
            / "static" / "admin.html").read_text(encoding="utf-8")
    code = html.replace("//   `typeof loadCustomers==='function' && loadCustomers()` 였는데 그런 함수는", "")
    assert "loadCustomers" not in code, "없는 함수를 다시 부르고 있다"
    assert "async function refreshCustomers()" in html, "갱신 함수가 사라졌다"
    # 갱신은 한 곳에서 정한다(0순위-B) — 실제 이름 둘을 그 안에서 부른다
    body = html.split("async function refreshCustomers()", 1)[1][:260]
    assert "load()" in body and "renderCustomers()" in body, body
