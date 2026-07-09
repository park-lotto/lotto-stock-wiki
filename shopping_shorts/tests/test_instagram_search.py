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
            "videoUrl": "https://scontent.cdninstagram.com/v.mp4",
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
    # resultsType 기본값(posts)은 사진·캐러셀 위주라 반드시 reels로 지정해야 한다
    # (2026-07-09 실측 버그 — 지정 안 하면 전부 사진이라 videoUrl이 비어있었음).
    assert captured["payload"]["resultsType"] == "reels"
    assert captured["actor"] == "apify~instagram-hashtag-scraper"


def test_search_skips_items_without_url(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"caption": "no url", "videoUrl": "v.mp4"},
            {"url": "https://www.instagram.com/p/x/", "caption": "t", "displayUrl": "d", "videoUrl": "v2.mp4"},
        ]
    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.instagram.com/p/x/"


def test_search_skips_photo_posts_without_video_url(monkeypatch):
    """resultsType=reels로 요청해도 사진 게시물이 섞여 나올 수 있어 videoUrl
    없는 항목은 걸러낸다(2026-07-09, "일치라고 나온 게 이미지 페이지" 버그 —
    resultsType 지정 전에는 검색결과 전부가 사진/캐러셀이라 존재하지도
    않는 영상을 후보로 잘못 보여주고 있었음)."""
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"url": "https://www.instagram.com/p/photo/", "caption": "사진", "displayUrl": "d", "videoUrl": None},
            {"url": "https://www.instagram.com/p/reel/", "caption": "영상", "displayUrl": "d2", "videoUrl": "v.mp4"},
        ]
    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.instagram.com/p/reel/"


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        instagram_search.search("x")
