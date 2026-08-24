"""세션 사망 근본수리 — ①계정↔프록시 짝 ②세션 생사 감시 (2026-08-24).

실사고: 레퍼런스 풀 7계정 중 3개가 인스타에 의해 회수(set-cookie: sessionid=deleted).
쿠키 만료일은 2027년이라 '만료'가 아니라 인스타의 능동 무효화였다.

원인: `_detail_context()`가 slots[0] **고정**인데다 프록시가 elif라 안 걸려,
0번 계정만 AWS 서버 맨 IP(43.200.48.69)로 매일 119~125건씩 나갔다.
나머지 6개는 한국 가정회선(kr-11~)으로 나가는데 0번만 데이터센터 IP였다.

⚠️ 로테이션만 붙이면 7계정이 서버IP를 돌려써 **전멸**한다 —
계정과 프록시는 반드시 **짝으로** 정한다(0순위-B).
"""
import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent


def _src(name):
    return (_SRC / name).read_text(encoding="utf-8")


# ── ① 계정↔프록시 짝 ──────────────────────────────────────────

def test_detail_context가_세션과_프록시를_함께_정한다():
    """★근본원인: 세션만 정하고 프록시를 안 붙이면 서버 맨 IP로 나간다.

    실측(2026-08-24): 직결=43.200.48.69(AWS) / 슬롯프록시=218.144.139.48(한국 가정).
    인스타는 '데이터센터에서 하루 수백 건 긁는 계정'으로 보고 세션을 회수한다.
    """
    src = _src("instagram_playwright.py")
    body = src[src.index("def _detail_context"):]
    body = body[:body.index("\ndef ")]
    assert "slot_proxy" in body, (
        "_detail_context가 slot_proxy를 안 쓴다 — 세션만 정하고 프록시가 없으면 "
        "그 계정만 서버 맨 IP로 나가 인스타가 회수한다(2026-08-24 실사고)")


def test_슬롯프록시가_세션분기에_막히지_않는다():
    """★옛 버그: `if session_path: … elif INSTAGRAM_PROXY:` 라 세션이 잡히면
    프록시 분기에 **영원히 도달하지 않았다**(0순위-B의 그 모양).

    슬롯 프록시는 세션과 짝이므로 세션 여부와 무관하게 걸려야 한다.
    (INSTAGRAM_PROXY 폴백은 풀이 비었을 때만 쓰는 옛 경로라 elif로 남겨둔다 —
     그쪽은 세션이 없을 때만 의미가 있어 동작이 바뀌지 않는다.)
    """
    src = _src("instagram_playwright.py")
    body = src[src.index("def _detail_context"):]
    body = body[:body.index('\ndef ')]
    assert re.search(r'\n    if _proxy_kw:', body), (
        "슬롯 프록시가 독립 if로 걸려 있지 않다 — 세션 분기에 먹히면 "
        "그 계정만 서버 맨 IP로 나간다"
    )

def test_계정과_프록시는_같은_인덱스로_정해진다():
    """짝이 어긋나면 '쓰던 사람이 갑자기 다른 집에서 접속'으로 보인다."""
    src = _src("instagram_playwright.py")
    body = src[src.index("def _detail_context"):]
    body = body[:body.index("\ndef ")]
    # 세션과 프록시를 같은 변수(인덱스)로 뽑아야 한다
    assert re.search(r"slot_proxy\(\s*_?i\w*\s*,", body), (
        "slot_proxy에 세션과 같은 인덱스를 넘기지 않는다 — 계정↔IP 1:1이 깨진다"
    )


# ── ② 세션 생사 감시 ───────────────────────────────────────────

def test_세션_생사판정_함수가_있다():
    from shopping_shorts import channel_archive as ca
    assert hasattr(ca, "session_alive"), (
        "session_alive가 없다 — 세션이 죽어도 로그엔 unknown으로만 찍혀 "
        "채널 탓으로 보인다(3개가 죽은 걸 2주간 아무도 몰랐다)"
    )


def test_live_slots가_인덱스를_보존한다():
    """★죽은 슬롯을 '지우면' 인덱스가 당겨져 남은 계정의 IP 배정이 전부 바뀐다.

    계정↔IP 1:1이 재배치되면 인스타 눈엔 접속지 변경으로 보인다.
    그래서 거르되 **원래 인덱스를 그대로 들고** 다녀야 한다.
    """
    from shopping_shorts import channel_archive as ca
    assert hasattr(ca, "live_slots"), "live_slots가 없다"
    probe = {"/p/a.json": True, "/p/b.json": False, "/p/c.json": True}
    out = ca.live_slots(list(probe), alive=probe.get)
    assert out == [(0, "/p/a.json"), (2, "/p/c.json")], (
        f"인덱스가 보존되지 않았다: {out} — 2번이 1번으로 당겨지면 IP가 뒤바뀐다"
    )


def test_live_slots는_전멸시_원본을_돌려준다():
    """전부 죽었다고 빈 목록을 주면 수집이 통째로 0건이 된다 —
    그 경우엔 차라리 기존 동작(전부 시도)이 낫다."""
    from shopping_shorts import channel_archive as ca
    slots = ["/p/a.json", "/p/b.json"]
    out = ca.live_slots(slots, alive=lambda _p: False)
    assert out == [(0, "/p/a.json"), (1, "/p/b.json")], (
        f"전멸 시 폴백이 없다: {out} — 판정이 틀렸을 때 수집이 통째로 죽는다"
    )
