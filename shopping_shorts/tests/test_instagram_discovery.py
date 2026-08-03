"""인스타 계정 발굴(해시태그 탐색) 집계 — 순수 함수 단위 테스트.
참여도(좋아요+댓글) 합산 방식으로 xiaohongshu_discovery와 동일 패턴(2026-07-30)."""
from shopping_shorts import instagram_discovery as disc


def _item(username, full_name="", is_verified=False, url="u",
          like_count=0, comment_count=0, play_count=0):
    return {"username": username, "full_name": full_name, "is_verified": is_verified,
            "url": url, "like_count": like_count, "comment_count": comment_count,
            "play_count": play_count}


_TAGS = {"주방": ["kitchengadgets"]}


def test_aggregates_by_username_and_sums_engagement():
    items = {
        "kitchengadgets": [
            _item("chef_a", "Chef A", like_count=10, comment_count=5),   # eng 15
            _item("chef_a", "Chef A", like_count=5, comment_count=5),    # eng 10 → 합 25, 2건
            _item("chef_b", "Chef B", like_count=100),                   # eng 100, 1건
        ],
    }
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_posts=1)
    by_user = {a["username"]: a for a in out}
    assert by_user["chef_a"]["engagement_sum"] == 25
    assert by_user["chef_a"]["post_count"] == 2
    assert by_user["chef_a"]["avg_engagement"] == 12.5
    assert by_user["chef_b"]["engagement_sum"] == 100


def test_min_posts_filters_flukes():
    items = {"kitchengadgets": [_item("a", like_count=1), _item("a", like_count=1),
                                _item("b", like_count=999)]}  # b는 1건 → min_posts=2에 걸러짐
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_posts=2)
    assert [a["username"] for a in out] == ["a"]


def test_blacklist_excluded_case_insensitive():
    items = {"kitchengadgets": [_item("Good1", like_count=5), _item("Good1", like_count=5),
                                _item("Bad1", like_count=5), _item("Bad1", like_count=5)]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_posts=2,
                                 blacklist={"bad1"})
    assert [a["username"] for a in out] == ["Good1"]


def test_sorted_by_engagement_desc_and_profile_url():
    items = {"kitchengadgets": [_item("low", like_count=1), _item("low", like_count=1),
                                _item("hi", like_count=50), _item("hi", like_count=50)]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_posts=2)
    assert [a["username"] for a in out] == ["hi", "low"]
    assert out[0]["profile_url"] == "https://www.instagram.com/hi/"


def test_items_without_username_dropped():
    items = {"kitchengadgets": [{"username": "", "full_name": "익명"},
                                {"username": None, "full_name": "익명2"}]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_posts=1)
    assert out == []


def test_one_hashtag_failing_does_not_kill_run():
    def flaky_search(tag):
        if tag == "kitchengadgets":
            raise RuntimeError("blocked")
        return [_item("survivor", like_count=10), _item("survivor", like_count=10)]
    tags = {"주방": ["kitchengadgets", "kitchenhacks"]}
    out = disc.discover_accounts(flaky_search, tags, min_posts=2)
    assert [a["username"] for a in out] == ["survivor"]


def test_categories_accumulate_across_hashtags():
    items = {"tagA": [_item("multi", like_count=10), _item("multi", like_count=10)],
             "tagB": [_item("multi", like_count=10)]}
    tags = {"cat1": ["tagA"], "cat2": ["tagB"]}
    out = disc.discover_accounts(lambda tag: items[tag], tags, min_posts=2)
    assert out[0]["categories"] == ["cat1", "cat2"]
    assert out[0]["post_count"] == 3
    assert out[0]["engagement_sum"] == 30


def test_view_sum_and_engagement_are_tracked_separately():
    """조회수는 참여도 합계에 안 섞인다(자릿수 차이가 커서 정렬을 조회수가 압도하지 않게)."""
    items = {"kitchengadgets": [
        _item("viral_low_eng", like_count=1, comment_count=0, play_count=1_000_000),
        _item("viral_low_eng", like_count=1, comment_count=0, play_count=1_000_000),
        _item("real_engager", like_count=500, comment_count=200, play_count=1000),
        _item("real_engager", like_count=500, comment_count=200, play_count=1000),
    ]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_posts=2)
    by_user = {a["username"]: a for a in out}
    assert by_user["real_engager"]["engagement_sum"] > by_user["viral_low_eng"]["engagement_sum"]
    assert by_user["viral_low_eng"]["view_sum"] == 2_000_000
