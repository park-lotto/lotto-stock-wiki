"""인스타 계정 발굴(해시태그 탐색) 집계 — 순수 함수 단위 테스트.
xiaohongshu_discovery 패턴과 동일(2026-07-30)."""
from shopping_shorts import instagram_discovery as disc


def _item(username, full_name="", is_verified=False, url="u"):
    return {"username": username, "full_name": full_name,
            "is_verified": is_verified, "url": url}


_TAGS = {"주방": ["kitchengadgets"]}


def test_aggregates_by_username_and_counts_appearances():
    items = {
        "kitchengadgets": [
            _item("chef_a", "Chef A"),
            _item("chef_a", "Chef A"),
            _item("chef_b", "Chef B"),
        ],
    }
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_appear=1)
    by_user = {a["username"]: a for a in out}
    assert by_user["chef_a"]["appear_count"] == 2
    assert by_user["chef_b"]["appear_count"] == 1


def test_min_appear_filters_flukes():
    items = {"kitchengadgets": [_item("a"), _item("a"), _item("b")]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_appear=2)
    assert [a["username"] for a in out] == ["a"]


def test_blacklist_excluded_case_insensitive():
    items = {"kitchengadgets": [_item("Good1"), _item("Good1"), _item("Bad1"), _item("Bad1")]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_appear=2,
                                 blacklist={"bad1"})
    assert [a["username"] for a in out] == ["Good1"]


def test_sorted_by_appear_count_desc_and_profile_url():
    items = {"kitchengadgets": [_item("low"), _item("low"),
                                _item("hi"), _item("hi"), _item("hi")]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_appear=2)
    assert [a["username"] for a in out] == ["hi", "low"]
    assert out[0]["profile_url"] == "https://www.instagram.com/hi/"


def test_items_without_username_dropped():
    items = {"kitchengadgets": [{"username": "", "full_name": "익명"},
                                {"username": None, "full_name": "익명2"}]}
    out = disc.discover_accounts(lambda tag: items[tag], _TAGS, min_appear=1)
    assert out == []


def test_one_hashtag_failing_does_not_kill_run():
    def flaky_search(tag):
        if tag == "kitchengadgets":
            raise RuntimeError("blocked")
        return [_item("survivor"), _item("survivor")]
    tags = {"주방": ["kitchengadgets", "kitchenhacks"]}
    out = disc.discover_accounts(flaky_search, tags, min_appear=2)
    assert [a["username"] for a in out] == ["survivor"]


def test_categories_accumulate_across_hashtags():
    items = {"tagA": [_item("multi"), _item("multi")], "tagB": [_item("multi")]}
    tags = {"cat1": ["tagA"], "cat2": ["tagB"]}
    out = disc.discover_accounts(lambda tag: items[tag], tags, min_appear=2)
    assert out[0]["categories"] == ["cat1", "cat2"]
    assert out[0]["appear_count"] == 3
