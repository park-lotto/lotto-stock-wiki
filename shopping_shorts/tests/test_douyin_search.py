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
        "play_url": "",
        "channel": "",
        "likes": None,
        "views": None,
        "duration": None,
        "is_short": True,
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


def test_search_extracts_channel_stats_and_duration(monkeypatch):
    """메타 추출 계약 — 2026-07-18 서버 실측 스키마(authorMeta.nickName·statistics.diggCount/
    playCount·videoMeta.duration(ms)·videoMeta.playUrl)를 고정한다."""
    monkeypatch.setattr(douyin_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.douyin.com/video/meta", "type": "video",
            "itemTitle": "청소기", "authorMeta": {"nickName": "小王", "name": "wang"},
            "statistics": {"diggCount": 5000, "playCount": 120000, "commentCount": 22},
            "videoMeta": {"cover": "t.jpg", "duration": 30000, "playUrl": "p.mp4"},
        }]
    monkeypatch.setattr(douyin_search, "_run_with_rotation", fake_run_with_rotation)

    r = douyin_search.search("청소기")[0]
    assert r["channel"] == "小王"
    assert r["likes"] == 5000
    assert r["views"] == 120000
    assert r["duration"] == 30   # 30000ms → 30s
    assert r["is_short"] is True
    assert r["play_url"] == "p.mp4"


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(douyin_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        douyin_search.search("x")
