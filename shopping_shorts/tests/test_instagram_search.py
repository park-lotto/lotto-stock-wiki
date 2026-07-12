import pytest
from shopping_shorts import instagram_search


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])
    captured = {}

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        captured["payload"] = payload
        captured["actor"] = actor
        return [{
            "code": "DYcgCgZPgHf",
            "is_video": True,
            "caption": {"text": "11 cm Deep Hole Marker Test"},
            "thumbnail_url": "https://scontent.cdninstagram.com/thumb.jpg",
        }]

    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("marker", max_results=10)

    assert results == [{
        "url": "https://www.instagram.com/reel/DYcgCgZPgHf/",
        "title": "11 cm Deep Hole Marker Test",
        "thumbnail": "https://scontent.cdninstagram.com/thumb.jpg",
    }]
    assert captured["payload"] == {"query": "marker", "maxPages": 1}
    assert captured["actor"] == "data-slayer~instagram-search-reels"


def test_search_skips_items_without_code(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"is_video": True, "caption": {"text": "no code"}, "thumbnail_url": "d"},
            {"code": "abc123", "is_video": True, "caption": {"text": "t"}, "thumbnail_url": "d"},
        ]
    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.instagram.com/reel/abc123/"


def test_search_skips_non_video_items(monkeypatch):
    """검색 결과에 사진 게시물이 섞여 나올 가능성 대비 이중 확인."""
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"code": "photo1", "is_video": False, "caption": {"text": "사진"}, "thumbnail_url": "d"},
            {"code": "vid1", "is_video": True, "caption": {"text": "영상"}, "thumbnail_url": "d"},
        ]
    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.instagram.com/reel/vid1/"


def test_search_respects_max_results(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{"code": f"v{i}", "is_video": True, "caption": {"text": "t"}, "thumbnail_url": "d"}
                for i in range(20)]
    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run_with_rotation)

    results = instagram_search.search("x", max_results=3)
    assert len(results) == 3


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        instagram_search.search("x")


def test_owner_username_tries_multiple_paths():
    assert instagram_search._owner_username({"user": {"username": "a"}}) == "a"
    assert instagram_search._owner_username({"owner": {"username": "b"}}) == "b"
    assert instagram_search._owner_username({"username": "c"}) == "c"
    assert instagram_search._owner_username({"ownerUsername": "d"}) == "d"
    assert instagram_search._owner_username({"foo": 1}) is None
    assert instagram_search._owner_username({"user": None}) is None


def test_search_channels_returns_username(monkeypatch):
    monkeypatch.setattr(instagram_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"code": "c1", "is_video": True, "user": {"username": "chan_a"},
             "caption": {"text": "주방템"}, "thumbnail_url": "t1"},
            {"code": "c2", "is_video": True, "caption": {"text": "no user"}, "thumbnail_url": "t2"},
        ]
    monkeypatch.setattr(instagram_search, "_run_with_rotation", fake_run)

    out = instagram_search.search_channels("주방템")
    assert out == [{"username": "chan_a",
                    "url": "https://www.instagram.com/reel/c1/",
                    "title": "주방템", "thumbnail": "t1"}]  # username 없는 c2는 제외
