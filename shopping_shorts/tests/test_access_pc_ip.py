"""공유 의심은 **PC IP만** 센다 (2026-08-31 사장님 "pc등록ip를 두개씩, 모바일은 상관없고").

★뿌리: 모바일은 IP가 계속 바뀐다(LTE↔와이파이·기지국 이동). 모바일 IP까지 세니
  혼자 쓰는 정상 회원도 7일이면 IP가 대여섯 개가 되어 공유 의심 빨간불이 켜졌다.
  IP로 돌려쓰기를 볼 수 있는 건 PC뿐이다.

여기서 잠그는 계약:
  1. PC는 집+회사 **2개까지 정상**, 3개째부터 의심
  2. 모바일 IP가 아무리 많아도 pc_ips를 못 올린다
  3. 판별은 _is_mobile_ua 한 곳 — 아이패드(Mobile 있음)·안드로이드 태블릿(없음) 둘 다 잡는다
  4. ips·devices는 예전 뜻 그대로다(화면이 참고로 보여준다)
"""
import pathlib
import tempfile

import pytest

from shopping_shorts.store import Store, _is_mobile_ua

PC_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
PC_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E Safari"
ANDROID = "Mozilla/5.0 (Linux; Android 14; SM-S918N) Chrome/120.0 Mobile Safari"
IPAD = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Version/17.0 Mobile/15E Safari"
GALAXY_TAB = "Mozilla/5.0 (Linux; Android 13; SM-X706B) Chrome/120.0 Safari"

DAY = "2026-08-31"


@pytest.fixture
def st():
    return Store(str(pathlib.Path(tempfile.mkdtemp()) / "t.db"))


@pytest.mark.parametrize("ua,mobile", [
    (PC_WIN, False), (PC_MAC, False), ("", False),
    (IPHONE, True), (ANDROID, True),
    (IPAD, True),               # ★사파리 아이패드 UA엔 Mobile이 있다
    (GALAXY_TAB, True),         # ★안드로이드 태블릿엔 Mobile이 없다 — 기기명으로 잡는다
])
def test_mobile_detection(ua, mobile):
    assert _is_mobile_ua(ua) is mobile, ua[:50]


def test_mobile_ips_do_not_count(st):
    """★모바일이 IP를 다섯 번 바꿔도 PC IP는 2개 그대로 — 정상이어야 한다."""
    for ip in ("1.1.1.1", "2.2.2.2"):
        st.record_access(1, ip, PC_WIN, DAY)
    for ip in ("10.0.0.%d" % n for n in range(1, 6)):
        st.record_access(1, ip, IPHONE, DAY)
    a = st.access_summary_all("2026-08-01")[1]
    assert a["pc_ips"] == 2, f"PC IP가 {a['pc_ips']} — 모바일이 섞였다"
    assert a["ips"] == 7, "전체 IP 수는 예전 뜻 그대로여야 한다"
    assert not (a["pc_ips"] >= 3), "정상 회원이 의심으로 잡힌다"


def test_three_pcs_is_still_suspicious(st):
    """★느슨해지기만 하면 안 된다 — 진짜 돌려쓰기는 여전히 잡혀야 한다."""
    for ip, ua in (("3.3.3.1", PC_WIN), ("3.3.3.2", PC_WIN), ("3.3.3.3", PC_MAC)):
        st.record_access(2, ip, ua, DAY)
    a = st.access_summary_all("2026-08-01")[2]
    assert a["pc_ips"] == 3 and a["pc_ips"] >= 3, "PC 3곳인데 의심이 안 된다"


def test_two_pcs_home_and_office_is_fine(st):
    """집+회사 = 정상(사장님이 정한 선)."""
    st.record_access(3, "1.2.3.4", PC_WIN, DAY)
    st.record_access(3, "5.6.7.8", PC_MAC, DAY)
    a = st.access_summary_all("2026-08-01")[3]
    assert a["pc_ips"] == 2 and a["pc_ips"] < 3


def test_summary_shape_has_all_three_keys(st):
    st.record_access(4, "9.9.9.9", PC_WIN, DAY)
    a = st.access_summary_all("2026-08-01")[4]
    assert set(a) == {"ips", "devices", "pc_ips"}, f"화면이 기대하는 칸이 아니다: {a}"
