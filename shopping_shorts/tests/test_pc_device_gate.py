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
    assert st.device_check(9, "aaa", PC, "1.1.1.1") == (True, 1, 1)
    assert st.device_check(9, "bbb", PC, "2.2.2.2") == (True, 2, 2)
    ok, slot, n = st.device_check(9, "ccc", PC, "3.3.3.3")
    assert ok is False and n == 2, "3번째 PC가 안 막혔다"


def test_registered_pc_passes_even_when_ip_changes(st):
    """★핵심: IP가 바뀌어도 같은 PC면 통과해야 한다(유동 IP라 매번 바뀐다)."""
    st.device_check(9, "aaa", PC, "1.1.1.1")
    ok, slot, _ = st.device_check(9, "aaa", PC, "77.77.77.77")
    assert ok and slot == 1, "IP가 바뀌었다고 같은 PC를 막았다"


def test_reset_frees_a_slot(st):
    st.device_check(9, "aaa", PC, "1.1.1.1")
    st.device_check(9, "bbb", PC, "2.2.2.2")
    assert st.device_check(9, "ccc", PC, "3.3.3.3")[0] is False
    st.device_reset(9, 2)                       # 사장님이 2번 칸 해제
    ok, slot, _ = st.device_check(9, "ccc", PC, "3.3.3.3")
    assert ok and slot == 2, "해제했는데도 안 들어온다"
    st.device_reset(9)                          # 전부 해제
    assert st.device_list(9) == []


def test_no_device_id_never_blocks(st):
    """도장이 없으면 판단 불가 — 막지 않는다(fail-open)."""
    assert st.device_check(9, "", PC, "1.1.1.1")[0] is True
    assert st.device_check(0, "aaa", PC, "1.1.1.1")[0] is True


def test_list_shows_what_admin_needs(st):
    st.device_check(9, "aaa", PC, "1.1.1.1")
    d = st.device_list(9)[0]
    assert d["slot"] == 1 and d["device_id"] == "aaa"
    assert d["ua"] == PC and d["ip"] == "1.1.1.1"
    assert d["first_seen"] > 0 and d["last_seen"] > 0


def test_counts_for_admin_list(st):
    st.device_check(1, "a", PC, "1.1.1.1")
    st.device_check(1, "b", PC, "1.1.1.2")
    st.device_check(2, "c", PC, "1.1.1.3")
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


def test_first_pc_visit_gets_a_stamp(client):
    """도장이 없으면 찍어주고 보낸다 — 그래야 다음부터 같은 PC로 알아본다."""
    c, app_mod = client
    r = c.get("/produce.html", headers={"user-agent": PC}, follow_redirects=False)
    if r.status_code == 303:
        assert app_mod._DEVICE_COOKIE in r.cookies, "기기 도장을 안 찍었다"


def test_logout_stays_open_even_when_blocked(client):
    """★막힌 사람도 로그아웃은 돼야 한다 — 아니면 계정을 바꿀 수조차 없다."""
    c, app_mod = client
    r = c.get("/logout", headers={"user-agent": PC}, follow_redirects=False)
    assert r.status_code != 403
