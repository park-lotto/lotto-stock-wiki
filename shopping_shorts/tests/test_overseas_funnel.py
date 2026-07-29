from shopping_shorts.overseas_funnel import passes_format, passes_relevance, under_view_ceiling, BLOCK_WORDS


def test_format_requires_url_and_id():
    assert passes_format({"url": "u", "video_id": "1"}) is True
    assert passes_format({"url": "", "video_id": "1"}) is False
    assert passes_format({"url": "u", "video_id": ""}) is False


def test_relevance_keeps_topical_even_without_exact_keyword():
    # 실측 2026-07-26: 이 제목들이 "kitchen gadgets" 완전구절이 아니란 이유로 버려졌었다
    # (반응 24만 포함). 검색으로 주제가 이미 보장되므로 차단어 없으면 살려야 한다.
    for t in ("New Kitchen Find", "Simple kitchen upgrades always end up being my favorite",
              "It's a knife, scissors & cutting board all in one", "这个太好用了！"):
        assert passes_relevance({"title": t}) is True, t


def test_relevance_blocks_junk_and_spam():
    assert passes_relevance({"title": "my dance challenge"}) is False   # 잡영상
    assert passes_relevance({"title": "giveaway! follow me"}) is False   # 스팸


def test_view_ceiling_only_applies_when_views_known():
    assert under_view_ceiling({"views": 500000}, ceiling=3000000) is True
    assert under_view_ceiling({"views": 9000000}, ceiling=3000000) is False
    assert under_view_ceiling({"views": 0}, ceiling=3000000) is True   # CN(뷰없음)은 통과


def test_block_words_present():
    assert "dance" in BLOCK_WORDS and "prank" in BLOCK_WORDS


def test_relevance_blocks_cn_ai_cartoon_spam():
    # 가전/도구에 섞여오던 AI 픽사풍 카툰(#动画创作工具 #动漫) 차단(실측 2026-07-26)
    assert passes_relevance({"title": "#动画创作工具 #动漫 #益智动画"}, ["小家电", "电器好物"]) is False


def test_shortform_filter():
    from shopping_shorts.overseas_funnel import passes_shortform
    assert passes_shortform({"duration": 57}) is True      # 숏폼
    assert passes_shortform({"duration": 181}) is False     # 롱폼 컷
    assert passes_shortform({"duration": None}) is True     # 길이불명은 통과
    assert passes_shortform({"duration": 120}) is True      # 경계값 통과


def test_caption_clutter_filter():
    from shopping_shorts.overseas_funnel import passes_caption_clutter
    assert passes_caption_clutter({"text_level": "heavy"}) is False   # 큰 자막이 화면 대부분 가림
    assert passes_caption_clutter({"text_level": "light"}) is True
    assert passes_caption_clutter({"text_level": "none"}) is True
    assert passes_caption_clutter({}) is True   # 아직 비전판정 안 된 항목은 통과(과필터 방지)


def test_caption_rank_orders_none_first():
    from shopping_shorts.overseas_funnel import caption_rank
    assert caption_rank({"text_level": "none"}) == 0
    assert caption_rank({"text_level": "light"}) == 1
    assert caption_rank({"text_level": "heavy"}) == 2


def test_caption_rank_unjudged_goes_last():
    """판정 없는 항목(비전 실패·썸네일 없음)은 light보다 뒤."""
    from shopping_shorts.overseas_funnel import caption_rank
    assert caption_rank({}) == 2
    assert caption_rank({"text_level": None}) == 2
