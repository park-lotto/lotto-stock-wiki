import urllib.parse
from shopping_shorts.search_links import build_search_links, lens_search_url


def test_build_search_links_uses_korean_for_kr_platforms_and_translated_for_cn():
    keywords = {"ko": ["바닥 끈적임 제거"], "en": ["floor stickiness remover"], "zh": ["地板黏腻清除剂"]}
    links = build_search_links(keywords)

    assert "youtube" in links and "google" in links and "tiktok" in links
    assert "instagram" in links and "douyin" in links and "xiaohongshu" in links

    kw_ko_encoded = urllib.parse.quote("바닥 끈적임 제거")
    assert any(kw_ko_encoded in u for u in links["youtube"])
    assert all(u.startswith("https://www.youtube.com/results?search_query=") for u in links["youtube"])

    kw_zh_encoded = urllib.parse.quote("地板黏腻清除剂")
    assert any(kw_zh_encoded in u for u in links["douyin"])
    assert any(kw_zh_encoded in u for u in links["xiaohongshu"])


def test_build_search_links_empty_keywords_returns_empty_lists():
    links = build_search_links({"ko": [], "en": [], "zh": []})
    assert links["youtube"] == []
    assert links["douyin"] == []


def test_lens_search_url_encodes_frame_url():
    url = lens_search_url("https://example.com/frame1.jpg")
    assert url.startswith("https://lens.google.com/uploadbyurl?url=")
    assert "https%3A%2F%2Fexample.com%2Fframe1.jpg" in url
