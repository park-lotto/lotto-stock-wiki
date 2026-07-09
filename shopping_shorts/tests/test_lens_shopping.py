import pytest

from shopping_shorts import lens_shopping


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_search_returns_normalized_matches(monkeypatch):
    monkeypatch.setattr(lens_shopping, "SERPAPI_KEY", "fake-key")
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({
            "visual_matches": [
                {"source": "Amazon.com", "title": "Cordless Hair Dryer",
                 "link": "https://amazon.com/x", "thumbnail": "https://t1.jpg"},
                {"source": "eBay", "title": "Body Dryer",
                 "link": "https://ebay.com/y", "thumbnail": "https://t2.jpg"},
            ]
        })

    monkeypatch.setattr(lens_shopping.requests, "get", fake_get)

    results = lens_shopping.search("https://example.com/frame.jpg")

    assert results == [
        {"source": "Amazon.com", "title": "Cordless Hair Dryer",
         "link": "https://amazon.com/x", "thumbnail": "https://t1.jpg"},
        {"source": "eBay", "title": "Body Dryer",
         "link": "https://ebay.com/y", "thumbnail": "https://t2.jpg"},
    ]
    assert captured["params"]["engine"] == "google_lens"
    assert captured["params"]["url"] == "https://example.com/frame.jpg"
    assert captured["params"]["api_key"] == "fake-key"


def test_search_skips_matches_without_link(monkeypatch):
    monkeypatch.setattr(lens_shopping, "SERPAPI_KEY", "fake-key")

    def fake_get(url, params=None, timeout=None):
        return _FakeResponse({"visual_matches": [
            {"source": "no link", "title": "t"},
            {"source": "ok", "title": "t2", "link": "https://x.com"},
        ]})

    monkeypatch.setattr(lens_shopping.requests, "get", fake_get)

    results = lens_shopping.search("https://example.com/frame.jpg")

    assert len(results) == 1
    assert results[0]["link"] == "https://x.com"


def test_search_no_matches_returns_empty(monkeypatch):
    monkeypatch.setattr(lens_shopping, "SERPAPI_KEY", "fake-key")

    def fake_get(url, params=None, timeout=None):
        return _FakeResponse({"search_metadata": {"status": "Success"}})

    monkeypatch.setattr(lens_shopping.requests, "get", fake_get)

    assert lens_shopping.search("https://example.com/frame.jpg") == []


def test_search_no_key_raises(monkeypatch):
    monkeypatch.setattr(lens_shopping, "SERPAPI_KEY", "")
    with pytest.raises(RuntimeError, match="SERPAPI_KEY"):
        lens_shopping.search("https://example.com/frame.jpg")
