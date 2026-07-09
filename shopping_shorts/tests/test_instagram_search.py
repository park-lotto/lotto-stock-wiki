import pytest
from shopping_shorts import instagram_search


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])
    captured = {}

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        captured["payload"] = payload
        captured["actor"] = actor
        return [{
            "url": "https://www.instagram.com/p/abc123/",
            "caption": "바닥 청소 완료!",
            "displayUrl": "https://scontent.cdninstagram.com/thumb.jpg",
        }]

    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("바닥 청소", max_results=10)

    assert results == [{
        "url": "https://www.instagram.com/p/abc123/",
        "title": "바닥 청소 완료!",
        "thumbnail": "https://scontent.cdninstagram.com/thumb.jpg",
    }]
    # 해시태그는 공백을 포함할 수 없어 제거해서 전달한다.
    assert captured["payload"]["hashtags"] == ["바닥청소"]
    assert captured["payload"]["resultsLimit"] == 10
    assert captured["actor"] == "apify~instagram-hashtag-scraper"


def test_search_skips_items_without_url(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"caption": "no url"},
            {"url": "https://www.instagram.com/p/x/", "caption": "t", "displayUrl": "d"},
        ]
    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.instagram.com/p/x/"


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        instagram_search.search("x")
