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


def test_search_full_returns_ranking_raw_schema(monkeypatch):
    """search_full은 build_tiktok_items가 그대로 소비하는 풀 raw 스키마를 반환한다
    (video_id/views/likes/comments/published_at/channel_title/title/thumbnail/url).
    minimal search()와 달리 랭킹 파이프라인에 바로 흘려넣기 위함."""
    monkeypatch.setattr(tiktok_search, "APIFY_TOKENS", ["fake-key"])
    captured = {}

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        captured["payload"] = payload
        captured["actor"] = actor
        return [{
            "id": "7412345678901234567",
            "text": "곰팡이 제거 꿀팁",
            "createTimeISO": "2026-07-12T09:30:00.000Z",
            "webVideoUrl": "https://www.tiktok.com/@clean/video/7412345678901234567",
            "playCount": 152000,
            "diggCount": 8400,
            "commentCount": 210,
            "authorMeta": {"name": "clean_life"},
            "videoMeta": {"coverUrl": "https://p16-sign.tiktokcdn.com/cover.jpeg", "duration": 42},
        }]

    monkeypatch.setattr(tiktok_search, "_run_with_rotation", fake_run_with_rotation)

    results = tiktok_search.search_full("곰팡이 제거", max_results=60)

    assert results == [{
        "video_id": "7412345678901234567",
        "url": "https://www.tiktok.com/@clean/video/7412345678901234567",
        "channel_title": "clean_life",
        "title": "곰팡이 제거 꿀팁",
        "thumbnail": "https://p16-sign.tiktokcdn.com/cover.jpeg",
        "published_at": "2026-07-12T09:30:00.000Z",
        "views": 152000,
        "likes": 8400,
        "comments": 210,
        "duration": 42,
        "media_platform": "tiktok",
    }]
    assert captured["payload"]["searchQueries"] == ["곰팡이 제거"]
    assert captured["payload"]["resultsPerPage"] == 60
    assert captured["actor"] == "clockworks~tiktok-scraper"


def test_search_full_skips_items_without_id(monkeypatch):
    """id 없는 아이템(썸네일만 있는 광고행 등)은 랭킹 키가 없어 제외."""
    monkeypatch.setattr(tiktok_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"text": "no id", "playCount": 100},
            {"id": "1", "text": "t", "webVideoUrl": "u",
             "authorMeta": {"name": "a"}, "videoMeta": {"coverUrl": "c"},
             "createTimeISO": "2026-07-12T00:00:00.000Z",
             "playCount": 5, "diggCount": 1, "commentCount": 0},
        ]
    monkeypatch.setattr(tiktok_search, "_run_with_rotation", fake_run_with_rotation)

    results = tiktok_search.search_full("x")

    assert len(results) == 1
    assert results[0]["video_id"] == "1"


def test_search_full_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(tiktok_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        tiktok_search.search_full("x")


def test_fetch_urls_uses_posturls_and_normalizes(monkeypatch):
    monkeypatch.setattr(tiktok_search, "APIFY_TOKENS", ["fake"])
    cap = {}
    def fake_run(payload, tokens, timeout, poll, actor=None):
        cap["payload"] = payload
        return [{"id": "9", "text": "t", "webVideoUrl": "https://tt/9",
                 "authorMeta": {"name": "a"}, "videoMeta": {"coverUrl": "c", "duration": 30},
                 "createTimeISO": "2026-07-20T00:00:00.000Z",
                 "playCount": 100, "diggCount": 10, "commentCount": 2}]
    monkeypatch.setattr(tiktok_search, "_run_with_rotation", fake_run)
    out = tiktok_search.fetch_urls(["https://tt/9"])
    assert cap["payload"]["postURLs"] == ["https://tt/9"]
    assert out[0]["video_id"] == "9" and out[0]["media_platform"] == "tiktok" and out[0]["views"] == 100


def test_fetch_urls_empty_returns_empty():
    assert tiktok_search.fetch_urls([]) == []
