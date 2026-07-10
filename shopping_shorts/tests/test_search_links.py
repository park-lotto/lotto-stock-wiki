import urllib.parse
from shopping_shorts.search_links import build_search_links, lens_search_url


def test_build_search_links_returns_platform_by_lang_urls():
    keywords = {
        "ko": ["바닥 끈적임 제거"], "en": ["floor stickiness remover"],
        "zh": ["地板黏腻清除剂"], "ja": ["床のべたつき除去"], "ru": ["удаление липкости пола"],
    }
    links = build_search_links(keywords)

    assert set(links.keys()) == {"youtube", "tiktok", "instagram", "xiaohongshu", "douyin"}
    for platform in links:
        assert set(links[platform].keys()) == {"ko", "en", "zh", "ja", "ru"}

    kw_ko_encoded = urllib.parse.quote("바닥 끈적임 제거")
    assert links["youtube"]["ko"] == f"https://www.youtube.com/results?search_query={kw_ko_encoded}"

    kw_zh_encoded = urllib.parse.quote("地板黏腻清除剂")
    assert kw_zh_encoded in links["douyin"]["zh"]
    assert kw_zh_encoded in links["xiaohongshu"]["zh"]


def test_build_search_links_uses_identified_product_name_first():
    """product_identify가 확인한 제품명이 키워드 맨 앞에 있으면 그걸로 링크를 만든다."""
    keywords = {"ko": ["reMarkable Paper Pro", "전자노트"], "en": ["reMarkable Paper Pro"],
                "zh": [], "ja": [], "ru": []}
    links = build_search_links(keywords)
    assert "reMarkable%20Paper%20Pro" in links["youtube"]["ko"]


def test_build_search_links_missing_language_omitted():
    links = build_search_links({"ko": [], "en": [], "zh": [], "ja": [], "ru": []})
    assert links["youtube"] == {}
    assert links["douyin"] == {}


def test_lens_search_url_encodes_frame_url():
    url = lens_search_url("https://example.com/frame1.jpg")
    assert url.startswith("https://lens.google.com/uploadbyurl?url=")
    assert "https%3A%2F%2Fexample.com%2Fframe1.jpg" in url
