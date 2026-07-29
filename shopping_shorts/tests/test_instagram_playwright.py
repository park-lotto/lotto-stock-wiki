"""Playwright 스크레이퍼의 오케스트레이션(진행률·집계·실패격리) 검증.

★실브라우저는 띄우지 않는다 — _scrape_one을 주입해 대체한다. 브라우저를 띄우면
테스트가 인스타 상태에 좌우돼 회귀 신호로 못 쓴다. 파싱은 test_instagram_parse가,
브라우저 동작은 서버 실측(10채널 게이트)이 각각 맡는다.
"""
from shopping_shorts import instagram_playwright as ipw


def _fake_ok(username):
    """(nodes, page_url, error) — 스크레이퍼 1채널 반환 계약."""
    return ([{"code": f"C_{username}", "taken_at": 1769500000}],
            f"https://www.instagram.com/{username}/reels/", None)


def _fake_login_wall(username):
    return ([], "https://www.instagram.com/accounts/login/?next=/x/", None)


def _fake_error(username):
    return ([], f"https://www.instagram.com/{username}/reels/", "Timeout 20000ms")


def test_fetch_reels_returns_ten_key_items():
    items = ipw.fetch_reels(["homeinon"], _scrape_one=_fake_ok)
    assert len(items) == 1
    assert set(items[0]) == {
        "shortcode", "url", "timestamp", "caption", "commentsCount",
        "likesCount", "videoViewCount", "displayUrl", "videoUrl", "ownerUsername",
    }
    assert items[0]["ownerUsername"] == "homeinon"


def test_one_channel_failure_does_not_kill_the_run():
    """★Apify 403이 전체를 죽이던 문제의 재발 방지 — 한 채널이 죽어도 나머지는 온다."""
    def _mixed(u):
        return _fake_error(u) if u == "bad" else _fake_ok(u)

    items = ipw.fetch_reels(["good1", "bad", "good2"], _scrape_one=_mixed)
    assert sorted(i["ownerUsername"] for i in items) == ["good1", "good2"]


def test_progress_callback_reports_every_channel():
    """★50분간 아무 표시가 없어 사장님이 취소했다 — 채널마다 진행률이 나가야 한다."""
    seen = []
    ipw.fetch_reels(["a", "b", "c"], on_progress=lambda *a: seen.append(a), _scrape_one=_fake_ok)
    assert len(seen) == 3
    done, total, items_so_far, tally = seen[-1]
    assert (done, total, items_so_far) == (3, 3, 3)
    assert tally["ok"] == 3


def test_tally_counts_each_classification():
    def _mixed(u):
        return {"w": _fake_login_wall, "e": _fake_error}.get(u, _fake_ok)(u)

    ipw.fetch_reels(["a", "w", "e"], _scrape_one=_mixed)
    assert ipw.LAST_TALLY["ok"] == 1
    assert ipw.LAST_TALLY["login_wall"] == 1
    assert ipw.LAST_TALLY["error"] == 1


def test_username_at_prefix_is_stripped():
    items = ipw.fetch_reels(["@homeinon"], _scrape_one=_fake_ok)
    assert items[0]["ownerUsername"] == "homeinon"


def test_empty_input_returns_empty_without_calling_scraper():
    called = []
    ipw.fetch_reels([], _scrape_one=lambda u: called.append(u) or _fake_ok(u))
    assert called == []
