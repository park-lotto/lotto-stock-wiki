"""발굴/정리 순수로직 테스트 — Apify 없이 의존성 주입으로 검증."""
from datetime import datetime, timezone, timedelta
from shopping_shorts import discovery


def test_new_usernames_excludes_known_and_dupes():
    cands = [
        {"username": "aaa"}, {"username": "BBB"}, {"username": "aaa"},
        {"username": "@ccc"}, {"username": None}, {"username": "ddd"},
    ]
    known = {"bbb"}  # 이미 아는 채널(소문자)
    out = discovery.new_usernames(cands, known)
    assert out == ["aaa", "@ccc", "ddd"]  # BBB 제외, 중복 aaa 1회, None 스킵, 순서보존


def test_new_usernames_respects_max():
    cands = [{"username": f"u{i}"} for i in range(30)]
    assert len(discovery.new_usernames(cands, set(), max_channels=5)) == 5


def test_discover_ranks_new_channels_by_comments():
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(hours=2)).isoformat()

    def search_fn(kw):
        assert kw == "주방템"
        return [{"username": "known_ch"}, {"username": "hot_ch"}, {"username": "mild_ch"}]

    def fetch_reels_fn(usernames):
        assert "known_ch" not in usernames  # 이미 아는 채널은 안 넘어옴
        return [
            {"ownerUsername": "hot_ch", "timestamp": recent, "commentsCount": 500,
             "shortcode": "h1", "caption": "주방 꿀템"},
            {"ownerUsername": "mild_ch", "timestamp": recent, "commentsCount": 30,
             "shortcode": "m1", "caption": "정리템"},
        ]

    items = discovery.discover(
        "주방템", known={"known_ch"}, search_fn=search_fn, fetch_reels_fn=fetch_reels_fn,
        prev_comments=lambda sc: None, prev_delta=lambda sc: None, now=now,
    )
    assert [i["username"] for i in items] == ["hot_ch", "mild_ch"]  # 댓글 내림차순
    assert all(i["discovered"] for i in items)
    assert items[0]["comments"] == 500


def test_discover_empty_when_no_new_channels():
    called = []
    items = discovery.discover(
        "x", known={"a", "b"},
        search_fn=lambda kw: [{"username": "a"}, {"username": "b"}],
        fetch_reels_fn=lambda u: called.append(u) or [],
        prev_comments=lambda sc: None, prev_delta=lambda sc: None,
    )
    assert items == []
    assert called == []  # 새 채널 없으면 Apify 수집 호출 자체를 안 함(비용 절약)


def test_discover_multi_aggregates_and_dedupes():
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(hours=1)).isoformat()
    searches = []

    def search_fn(kw):
        searches.append(kw)
        return {  # 카테고리별 후보(일부 중복 chX)
            "#주방템": [{"username": "chA"}, {"username": "chB"}],
            "#살림템": [{"username": "chB"}, {"username": "known1"}, {"username": "chC"}],
        }.get(kw, [])

    fetched = {}
    def fetch_reels_fn(usernames):
        fetched["u"] = usernames
        return [{"ownerUsername": u, "timestamp": recent, "commentsCount": 100,
                 "shortcode": u + "1"} for u in usernames]

    items = discovery.discover_multi(
        ["#주방템", "#살림템"], known={"known1"},
        search_fn=search_fn, fetch_reels_fn=fetch_reels_fn,
        prev_comments=lambda sc: None, prev_delta=lambda sc: None, now=now,
    )
    assert searches == ["#주방템", "#살림템"]           # 두 카테고리 모두 검색
    assert fetched["u"] == ["chA", "chB", "chC"]        # 중복 chB 1회, known1 제외
    assert len(items) == 3


def test_find_inactive_flags_channels_with_no_reels():
    channels = [
        {"name": "살아있음", "username": "alive"},
        {"name": "죽음1", "username": "Dead1"},
        {"name": "죽음2", "username": "@dead2"},
    ]
    active = {"alive", "someone_else"}
    out = discovery.find_inactive(channels, active)
    assert out == [
        {"name": "죽음1", "username": "Dead1"},
        {"name": "죽음2", "username": "@dead2"},
    ]
