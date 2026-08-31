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
                 "/api/my/devices", "/api/my/devices/register", "/setup"):
        assert app_mod._pc_gate_open_path(path), f"{path}가 막히면 등록할 길이 없다"
    # 정작 막아야 할 길은 열려 있으면 안 된다
    for path in ("/produce.html", "/api/mix/start", "/api/produce/mix/render"):
        assert not app_mod._pc_gate_open_path(path), f"{path}가 통째로 열려 있다"
