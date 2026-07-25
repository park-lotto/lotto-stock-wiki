from shopping_shorts.overseas_funnel import passes_format, passes_relevance, under_view_ceiling, BLOCK_WORDS


def test_format_requires_url_and_id():
    assert passes_format({"url": "u", "video_id": "1"}) is True
    assert passes_format({"url": "", "video_id": "1"}) is False
    assert passes_format({"url": "u", "video_id": ""}) is False


def test_relevance_allow_and_block():
    assert passes_relevance({"title": "kitchen gadget you need"}, ["kitchen", "gadget"]) is True
    assert passes_relevance({"title": "my dance challenge"}, ["kitchen"]) is False   # 차단어
    assert passes_relevance({"title": "random vlog"}, ["kitchen"]) is False           # 허용어 없음
    assert passes_relevance({"title": "厨房神器好物"}, ["厨房", "神器"]) is True       # 중국어 허용어


def test_view_ceiling_only_applies_when_views_known():
    assert under_view_ceiling({"views": 500000}, ceiling=3000000) is True
    assert under_view_ceiling({"views": 9000000}, ceiling=3000000) is False
    assert under_view_ceiling({"views": 0}, ceiling=3000000) is True   # CN(뷰없음)은 통과


def test_block_words_present():
    assert "dance" in BLOCK_WORDS and "prank" in BLOCK_WORDS
