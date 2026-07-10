import pytest
from shopping_shorts import douyin_search


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(douyin_search, "APIFY_TOKENS", ["fake-key"])
    captured = {}

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        captured["payload"] = payload
        captured["actor"] = actor
        return [{
            "url": "https://www.douyin.com/video/123",
            "type": "video",
            "itemTitle": "iPhone 17 리뷰",
            "videoMeta": {"cover": "https://p3-sign.douyinpic.com/thumb.jpg"},
        }]

    monkeypatch.setattr(douyin_search, "_run_with_rotation", fake_run_with_rotation)

    results = douyin_search.search("iphone", max_results=10)

    assert results == [{
        "url": "https://www.douyin.com/video/123",
        "title": "iPhone 17 리뷰",
        "thumbnail": "https://p3-sign.douyinpic.com/thumb.jpg",
    }]
    assert captured["payload"]["keywords"] == ["iphone"]
    assert captured["payload"]["maxResultsPerQuery"] == 10
    assert captured["actor"] == "zen-studio~douyin-search-scraper"


def test_search_falls_back_to_text_when_no_item_title(monkeypatch):
    monkeypatch.setattr(douyin_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{"url": "https://www.douyin.com/video/x", "type": "video",
                  "itemTitle": "", "text": "본문 텍스트", "videoMeta": {"cover": "t.jpg"}}]
    monkeypatch.setattr(douyin_search, "_run_with_rotation", fake_run_with_rotation)

    results = douyin_search.search("x")
    assert results[0]["title"] == "본문 텍스트"


def test_search_skips_non_video_items(monkeypatch):
    monkeypatch.setattr(douyin_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"url": "https://www.douyin.com/note/photo", "type": "image", "itemTitle": "사진"},
            {"url": "https://www.douyin.com/video/vid", "type": "video", "itemTitle": "영상",
             "videoMeta": {"cover": "t.jpg"}},
        ]
    monkeypatch.setattr(douyin_search, "_run_with_rotation", fake_run_with_rotation)

    results = douyin_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.douyin.com/video/vid"


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(douyin_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        douyin_search.search("x")
