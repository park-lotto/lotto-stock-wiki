# -*- coding: utf-8 -*-
"""2026-08-17 수리 3건을 못 박는다.

배경(실측): 릴스 목록 XHR을 고정 2.5초만 기다리고 없으면 빈손으로 나가던 탓에
같은 채널이 될 때·안 될 때가 무작위였다. 같은 슬롯·같은 14채널 대조에서
2.5초 5/14 → 10초 14/14였고, 수확 0이던 채널 30개는 15초에서 30/30 전부 회수됐다.
그때 실패는 'not_found'로 집계돼 "채널이 없어졌다"로 두 번 오독됐다(08-09, 08-17).
"""
import pytest

from shopping_shorts import config, instagram_playwright as ip
from shopping_shorts.instagram_parse import classify_channel_result


def test_빈결과는_not_found가_아니라_unknown이다():
    """이름이 원인을 단정하면 사람이 엉뚱한 데를 판다.

    여기는 판정이 아니라 나머지 통이다 — 채널이 없는지 확인하는 코드는 없다.
    """
    assert classify_channel_result([], "https://www.instagram.com/u/reels/", None) == "unknown"


def test_로그인벽은_여전히_따로_갈린다():
    """unknown으로 뭉뚱그리면 안 된다 — 로그인벽은 계정 교체로 뚫리고 대처가 정반대다."""
    gate = classify_channel_result(
        [], "https://www.instagram.com/challenge/action/update_risky_contactpoint/", None)
    assert gate == "login_wall"


def test_대기상한은_설정으로_바꿀_수_있고_기본이_2500보다_길다():
    """2.5초가 실패 55%의 원인이었다. 기본값이 다시 그 밑으로 내려가면 사고가 재발한다."""
    assert config.INSTAGRAM_PW_LIST_WAIT_MS > 2500


def test_채널별_판정이_목록으로_남는다():
    """숫자만 남기면 '어느 채널이 실패했나'를 못 되살린다(08-17 조사 불가 사고).

    실패 채널 이름과 도달 URL이 LAST_VERDICTS에 남아야 바로 재시도할 수 있다.
    """
    calls = {"n": 0}

    def fake(username, session_path=None, proxy=None):
        calls["n"] += 1
        if username == "good":
            return [{"pk": "1", "code": "abc"}], f"https://www.instagram.com/{username}/reels/", None
        return [], f"https://www.instagram.com/{username}/reels/", None

    ip.fetch_reels(["good", "bad"], _scrape_one=fake)

    got = {u: v for u, v, _ in ip.LAST_VERDICTS}
    assert got == {"good": "ok", "bad": "unknown"}
    # URL도 함께 남아야 신종 관문을 다음에 알아볼 수 있다
    urls = {u: url for u, _, url in ip.LAST_VERDICTS}
    assert urls["bad"].endswith("/bad/reels/")
    assert ip.LAST_TALLY["ok"] == 1 and ip.LAST_TALLY["unknown"] == 1


def test_집계_키에_not_found가_남아있지_않다():
    """옛 이름이 섞여 있으면 화면·보고가 두 이름을 오가며 또 헷갈린다."""
    ip.fetch_reels([], _scrape_one=lambda *a, **k: ([], "", None))
    assert "not_found" not in ip.LAST_TALLY
    assert "unknown" in ip.LAST_TALLY
