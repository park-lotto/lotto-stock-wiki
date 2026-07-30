"""발굴 해시태그 → 카테고리 물려주기(2026-07-30).

신규 발굴 채널은 과거 이력도 캡션도 없어 랭킹에서 전부 '기타'로 보였다.
채널을 찾아낸 태그가 곧 카테고리 힌트라 추가 크롤 없이 채울 수 있다.
"""
from shopping_shorts import discovery
from shopping_shorts.categorize import category_of_hashtag


def test_hashtag_to_category():
    assert category_of_hashtag("#주방템") == "홈템"
    assert category_of_hashtag("정리수납") == "홈템"      # # 없어도 동작
    assert category_of_hashtag("#자취요리") == "레시피"
    assert category_of_hashtag("#뷰티템") == "뷰티"


def test_unmappable_hashtag_returns_empty_not_wrong_category():
    # 우리 5개 카테고리에 대응이 없는 태그는 억지로 넣지 않는다
    assert category_of_hashtag("#육아템") == ""
    assert category_of_hashtag("") == ""
    assert category_of_hashtag(None) == ""


def test_discover_multi_tags_each_channel_with_its_source_hashtag():
    def search_fn(kw):
        return {"#주방템": [{"username": "kitchen_a"}],
                "#자취요리": [{"username": "cook_b"}]}[kw]

    def fetch_reels_fn(users):
        return [{"ownerUsername": u, "shortcode": f"sc_{u}", "timestamp": "2026-07-30T09:00:00Z",
                 "commentsCount": 5} for u in users]

    from datetime import datetime, timezone
    items = discovery.discover_multi(
        ["#주방템", "#자취요리"], known=set(), search_fn=search_fn,
        fetch_reels_fn=fetch_reels_fn, prev_comments=lambda s: None,
        prev_delta=lambda s: None, now=datetime(2026, 7, 30, 12, tzinfo=timezone.utc),
        search_workers=1)
    tags = {i["username"]: i["discover_tag"] for i in items}
    assert tags == {"kitchen_a": "#주방템", "cook_b": "#자취요리"}
