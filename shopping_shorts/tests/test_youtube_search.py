import pytest
from shopping_shorts import youtube_search


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEY", "fake-key")

    def fake_get(url, params, timeout):
        assert params["q"] == "floor cleaner"
        assert params["key"] == "fake-key"
        class FakeResp:
            def json(self):
                return {"items": [
                    {"id": {"videoId": "abc123"},
                     "snippet": {"title": "Floor Cleaner Review",
                                 "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/abc123/mq.jpg"}}}},
                ]}
            def raise_for_status(self): pass
        return FakeResp()
    monkeypatch.setattr(youtube_search.requests, "get", fake_get)

    results = youtube_search.search("floor cleaner", max_results=10)

    assert results == [{
        "url": "https://www.youtube.com/watch?v=abc123",
        "title": "Floor Cleaner Review",
        "thumbnail": "https://i.ytimg.com/vi/abc123/mq.jpg",
    }]


def test_search_no_key_raises(monkeypatch):
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEY", "")
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
        youtube_search.search("x")
