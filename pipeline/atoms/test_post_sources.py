import pytest
from pipeline.atoms.post_sources import source_config


def test_blog_config():
    c = source_config("blog")
    assert c["source_type"] == "blog"
    assert c["dir"] == "raw/blog"
    assert c["header_label"] == "출처"
    assert c["registry"] == "blog_registry.json"


def test_youtube_config():
    c = source_config("youtube")
    assert c["source_type"] == "youtube"
    assert c["dir"] == "raw/yt"
    assert c["header_label"] == "채널"
    assert c["registry"] == "youtube_registry.json"


def test_news_config():
    c = source_config("news")
    assert c["source_type"] == "news"
    assert c["dir"] == "raw/news"
    assert c["header_label"] == ["출처", "키워드"]
    assert c["registry"] == "news_registry.json"


def test_unknown_source_raises():
    with pytest.raises(KeyError):
        source_config("듣보소스")
