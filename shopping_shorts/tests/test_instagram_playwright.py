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
    # ownerFullName 추가(2026-08-06) — parse_reel_node가 채널 표시명을 같이 싣는다
    # (아카이브 카드 한글 이름용, 추가 요청 0건). 같은 파서를 타므로 여기도 한 키 늘었다.
    assert set(items[0]) == {
        "shortcode", "url", "timestamp", "caption", "commentsCount",
        "likesCount", "videoViewCount", "displayUrl", "videoUrl", "ownerUsername",
        "ownerFullName",
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


# ── search_channels: instagram_search.search_channels(Apify)와 동일 계약의
# 무료 어댑터(2026-07-30, "신규채널 픽업" discover.html 전환용) ──
def test_search_channels_shape_via_monkeypatch(monkeypatch):
    def _fake_search_hashtag(tag):
        assert tag == "주방템"   # "#주방템" → "#" 제거된 순수 태그로 전달
        return [{"username": "chef_a", "full_name": "Chef A", "is_verified": True,
                 "url": "https://www.instagram.com/p/X/", "like_count": 10}]
    monkeypatch.setattr(ipw, "search_hashtag", _fake_search_hashtag)
    out = ipw.search_channels("#주방템")
    assert out == [{"username": "chef_a", "url": "https://www.instagram.com/p/X/",
                    "title": "Chef A", "thumbnail": ""}]


def test_search_channels_empty_keyword_returns_empty(monkeypatch):
    called = []
    monkeypatch.setattr(ipw, "search_hashtag", lambda tag: called.append(tag) or [])
    assert ipw.search_channels("") == []
    assert ipw.search_channels("#") == []
    assert called == []


def test_search_channels_respects_max_results(monkeypatch):
    monkeypatch.setattr(ipw, "search_hashtag",
                        lambda tag: [{"username": f"u{i}"} for i in range(10)])
    out = ipw.search_channels("주방템", max_results=3)
    assert len(out) == 3


# ── fetch_profiles: apify_client.fetch_profiles(유료)와 동일 계약의 무료 어댑터 ──
def test_fetch_profiles_maps_to_apify_compatible_shape():
    def _fake_fetch_all(usernames):
        return {u.lower(): {"followers": 100, "posts": 5, "full_name": f"Name {u}"} for u in usernames}
    out = ipw.fetch_profiles(["@Chef_A", "chef_b"], _fetch_all=_fake_fetch_all)
    assert out == {
        "chef_a": {"followers": 100, "posts": 5, "full_name": "Name Chef_A"},
        "chef_b": {"followers": 100, "posts": 5, "full_name": "Name chef_b"},
    }


def test_fetch_profiles_empty_input_returns_empty():
    called = []
    out = ipw.fetch_profiles([], _fetch_all=lambda us: called.append(us) or {})
    assert out == {}
    assert called == []
