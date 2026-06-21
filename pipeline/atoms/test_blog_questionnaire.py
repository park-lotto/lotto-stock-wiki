"""Tests for blog_questionnaire module (라우팅+질문지)."""
from pipeline.atoms.blog_questionnaire import blog_trust, BLOG_PROMPT


def test_registered_blogger_trust():
    assert blog_trust("pokara61") == "B"


def test_unregistered_blogger_default_c():
    assert blog_trust("듣보블로거") == "C"


def test_prompt_has_router_and_types():
    # 내용 라우팅 + 4타입 + sector + quote 포함
    for kw in ("target_kind", "stock_tips", "sector", "market", "insight", "quote"):
        assert kw in BLOG_PROMPT


def test_prompt_injects_sector_taxonomy():
    from pipeline.atoms.sector_classify import sectors_list
    assert sectors_list()[0] in BLOG_PROMPT  # "반도체"


def test_extract_blog_importable():
    from pipeline.atoms.blog_questionnaire import extract_blog
    assert callable(extract_blog)
