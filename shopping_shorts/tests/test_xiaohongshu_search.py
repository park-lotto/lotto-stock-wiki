import pytest
from shopping_shorts import xiaohongshu_search


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])
    captured = {}

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        captured["payload"] = payload
        captured["actor"] = actor
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/abc123",
            "type": "video",
            "title": "실링팬 개봉기",
            "video": {"url_720p": "https://sns-video.xhscdn.com/v.mp4", "thumbnail": "https://sns.xhscdn.com/t.jpg"},
        }]

    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    results = xiaohongshu_search.search("실링팬", max_results=10)

    assert results == [{
        "url": "https://www.xiaohongshu.com/discovery/item/abc123",
        "title": "실링팬 개봉기",
        "thumbnail": "https://sns.xhscdn.com/t.jpg",
        "play_url": "https://sns-video.xhscdn.com/v.mp4",
        "channel": "",
        "likes": None,
        "views": None,
        "duration": None,
        "is_short": True,
    }]
    assert captured["payload"]["keywords"] == ["실링팬"]
    assert captured["payload"]["maxResults"] == 10
    assert captured["payload"]["noteType"] == "video"
    assert captured["actor"] == "zen-studio~rednote-search-scraper"


def test_search_falls_back_to_desc_when_title_empty(monkeypatch):
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/x",
            "type": "video", "title": "", "desc": "설명만 있음",
            "video": {"url_720p": "v.mp4", "thumbnail": "t.jpg"},
        }]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    results = xiaohongshu_search.search("x")
    assert results[0]["title"] == "설명만 있음"


def test_search_skips_image_notes_without_video(monkeypatch):
    """noteType=video로 요청해도 사진 노트가 섞여 나올 가능성 대비 이중 확인."""
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"url": "https://www.xiaohongshu.com/discovery/item/photo", "type": "image", "title": "사진", "video": {}},
            {"url": "https://www.xiaohongshu.com/discovery/item/vid", "type": "video", "title": "영상",
             "video": {"url_720p": "v.mp4", "thumbnail": "t.jpg"}},
        ]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    results = xiaohongshu_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.xiaohongshu.com/discovery/item/vid"


def test_search_extracts_channel_likes_and_duration(monkeypatch):
    """메타(채널명·좋아요·영상길이·숏폼여부) 추출 계약 — 가정한 필드명을 고정한다."""
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/meta",
            "type": "video", "title": "청소기 리뷰",
            "user": {"nickname": "살림요정"},
            "interactInfo": {"likedCount": "1200", "viewCount": 30000},
            "video": {"url_720p": "v.mp4", "thumbnail": "t.jpg", "duration": 240},
        }]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    r = xiaohongshu_search.search("청소기")[0]
    assert r["channel"] == "살림요정"
    assert r["likes"] == 1200
    assert r["views"] == 30000
    assert r["duration"] == 240
    assert r["is_short"] is False   # 240초 > 90초


def test_duration_in_milliseconds_is_normalized(monkeypatch):
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/ms",
            "type": "video", "title": "짧은거",
            "video": {"url_720p": "v.mp4", "thumbnail": "t.jpg", "duration": 45000},
        }]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    r = xiaohongshu_search.search("x")[0]
    assert r["duration"] == 45   # 45000ms → 45s
    assert r["is_short"] is True


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        xiaohongshu_search.search("x")
