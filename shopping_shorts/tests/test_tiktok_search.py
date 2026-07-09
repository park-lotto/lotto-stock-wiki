import pytest
from shopping_shorts import tiktok_search


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(tiktok_search, "APIFY_TOKENS", ["fake-key"])
    captured = {}

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        captured["payload"] = payload
        captured["actor"] = actor
        return [{
            "webVideoUrl": "https://www.tiktok.com/@user/video/123",
            "text": "바닥 청소 꿀팁",
            "videoMeta": {"coverUrl": "https://p16-sign.tiktokcdn.com/cover.jpeg"},
        }]

    monkeypatch.setattr(tiktok_search, "_run_with_rotation", fake_run_with_rotation)

    results = tiktok_search.search("바닥 청소", max_results=10)

    assert results == [{
        "url": "https://www.tiktok.com/@user/video/123",
        "title": "바닥 청소 꿀팁",
        "thumbnail": "https://p16-sign.tiktokcdn.com/cover.jpeg",
    }]
    assert captured["payload"]["searchQueries"] == ["바닥 청소"]
    assert captured["payload"]["resultsPerPage"] == 10
    assert captured["actor"] == "clockworks~tiktok-scraper"


def test_search_skips_items_without_video_url(monkeypatch):
    monkeypatch.setattr(tiktok_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"text": "no url here", "videoMeta": {}},
            {"webVideoUrl": "https://www.tiktok.com/@u/video/1", "text": "t", "videoMeta": {"coverUrl": "c"}},
        ]
    monkeypatch.setattr(tiktok_search, "_run_with_rotation", fake_run_with_rotation)

    results = tiktok_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.tiktok.com/@u/video/1"


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(tiktok_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        tiktok_search.search("x")
