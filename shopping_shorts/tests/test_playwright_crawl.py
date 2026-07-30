import pytest
from datetime import datetime, timezone

from shopping_shorts import playwright_crawl as pc


def test_parse_publish_time_hours_ago():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    assert pc._parse_publish_time("11小时前", now=now) == "2026-07-29T01:00:00Z"


def test_parse_publish_time_month_day_assumes_current_year():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    assert pc._parse_publish_time("07-20", now=now) == "2026-07-20T12:00:00Z"


def test_parse_publish_time_full_date():
    assert pc._parse_publish_time("2025-09-22") == "2025-09-22T12:00:00Z"


def test_parse_publish_time_unrecognized_returns_empty():
    assert pc._parse_publish_time("") == ""
    assert pc._parse_publish_time(None) == ""
    assert pc._parse_publish_time("알수없음") == ""


def test_parse_publish_time_yesterday_with_clock():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    assert pc._parse_publish_time("昨天 23:51", now=now) == "2026-07-28T23:51:00Z"


def test_parse_publish_time_today_with_clock():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    assert pc._parse_publish_time("今天 08:05", now=now) == "2026-07-29T08:05:00Z"


def _note(note_id, media_type="video", display_title="厨房神器", xsec="tok123",
          liked="1200", comments="30", collected="90", shared="7",
          nickname="살림요정", cover="https://cover.jpg", pub_text="07-20",
          model_type="note"):
    return {
        "id": note_id,
        "model_type": model_type,
        "xsec_token": xsec,
        "note_card": {
            "type": media_type,
            "display_title": display_title,
            "corner_tag_info": [{"type": "publish_time", "text": pub_text}],
            "user": {"nickname": nickname, "user_id": "u1"},
            "interact_info": {"liked_count": liked, "comment_count": comments,
                               "collected_count": collected, "shared_count": shared},
            "cover": {"url_default": cover},
        },
    }


def test_xhs_follower_count_from_interactions():
    from shopping_shorts import xiaohongshu_playwright as xp
    # 2026-07-29 서버 실측 구조: user.userPageData.result.interactions[type=fans].count
    user = {"userPageData": {"result": {"interactions": [
        {"type": "follows", "count": "10"},
        {"type": "fans", "name": "Followers", "count": "232964"},
        {"type": "interaction", "count": "999"}]}}}
    assert xp._follower_count(user) == 232964
    assert xp._follower_count({}) == 0            # 없으면 0(가짜숫자 안 만듦)


def test_xhs_fetch_follower_counts_keys_by_userid():
    from shopping_shorts import xiaohongshu_playwright as xp
    fake = {"https://www.rednote.com/user/profile/u1": (500, None),
            "https://www.rednote.com/user/profile/u2": (0, "err")}
    out = xp.fetch_follower_counts(list(fake), _scrape_one=lambda url: fake[url])
    assert out == {"u1": 500, "u2": 0}


def test_parse_search_response_maps_real_schema():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    body = {"data": {"items": [_note("abc123")]}}
    out = pc._parse_search_response(body, now=now)
    assert out == [{
        "video_id": "abc123",
        "title": "厨房神器",
        "published_at": "2026-07-20T12:00:00Z",
        "views": 0,
        "likes": 1200,
        "comments": 30,
        "collects": 90,
        "shares": 7,
        "channel_title": "살림요정",
        "channel_id": "u1",   # 계정 발굴·프로필URL 조립용(user.user_id)
        "thumbnail": "https://cover.jpg",
        "url": "https://www.rednote.com/search_result/abc123?xsec_token=tok123&type=video",
        "media_platform": "xiaohongshu",
        "duration": None,
    }]


def test_parse_search_response_skips_non_video_notes():
    body = {"data": {"items": [_note("photo1", media_type="normal")]}}
    assert pc._parse_search_response(body) == []


def test_parse_search_response_skips_ad_slots_without_note_card():
    body = {"data": {"items": [
        {"id": "ad-slot#12345", "model_type": None},
        _note("real1"),
    ]}}
    out = pc._parse_search_response(body)
    assert len(out) == 1 and out[0]["video_id"] == "real1"


def test_parse_search_response_skips_unparseable_publish_time():
    body = {"data": {"items": [_note("x", pub_text="알수없음")]}}
    assert pc._parse_search_response(body) == []


def test_parse_search_response_handles_empty_data():
    assert pc._parse_search_response({}) == []
    assert pc._parse_search_response(None) == []


def test_sort_forcer_rewrites_body_sort():
    # 발굴은 general(인기순), 해외HOT은 time_descending으로 body.sort를 바꿔치기.
    captured = {}
    class _Req:
        url = "https://x/api/sns/web/v1/search/notes?..."; method = "POST"; post_data = '{"keyword":"k"}'
    class _Route:
        def continue_(self, post_data=None): captured["post_data"] = post_data
    import json
    pc._make_sort_forcer("general")(_Route(), _Req())
    assert json.loads(captured["post_data"])["sort"] == "general"


def test_search_full_uses_injected_crawl_and_dedups(monkeypatch, tmp_path):
    session_file = tmp_path / "session.json"
    session_file.write_text("{}")

    def fake_crawl(keyword, session_path, timeout_ms, sort=None):
        assert keyword == "厨房神器"
        assert session_path == str(session_file)
        return [
            {"data": {"items": [_note("a"), _note("b")]}},
            {"data": {"items": [_note("a")]}},   # 중복 응답(재요청 등)
        ]

    out = pc.search_full("厨房神器", max_results=40, session_path=str(session_file), _crawl=fake_crawl)
    ids = [o["video_id"] for o in out]
    assert ids.count("a") == 1
    assert set(ids) == {"a", "b"}


def test_search_full_respects_max_results(monkeypatch, tmp_path):
    session_file = tmp_path / "session.json"
    session_file.write_text("{}")

    def fake_crawl(keyword, session_path, timeout_ms, sort=None):
        return [{"data": {"items": [_note(str(i)) for i in range(10)]}}]

    out = pc.search_full("kw", max_results=3, session_path=str(session_file), _crawl=fake_crawl)
    assert len(out) == 3


def test_search_full_returns_empty_when_session_missing(tmp_path):
    missing = tmp_path / "nope.json"
    out = pc.search_full("kw", session_path=str(missing), _crawl=lambda *a: pytest.fail("should not crawl"))
    assert out == []
