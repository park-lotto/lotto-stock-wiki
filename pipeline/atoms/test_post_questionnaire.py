"""테스트: post_questionnaire (blog_questionnaire 일반화)."""
from pipeline.atoms.post_questionnaire import POST_PROMPT, post_trust


def test_post_trust_blog_registry():
    assert post_trust("blog_registry.json", "pokara61") == "B"


def test_post_trust_youtube_registry():
    assert post_trust("youtube_registry.json", "UP_CYCLE_STOCK") == "B"


def test_post_trust_unregistered_default_c():
    assert post_trust("blog_registry.json", "듣보") == "C"


def test_post_prompt_structure():
    for kw in ("target_kind", "stock_tips", "sector", "market", "insight", "quote"):
        assert kw in POST_PROMPT


def test_post_prompt_injects_sector_taxonomy():
    from pipeline.atoms.sector_classify import sectors_list
    assert sectors_list()[0] in POST_PROMPT


def test_extract_post_importable():
    from pipeline.atoms.post_questionnaire import extract_post
    assert callable(extract_post)
