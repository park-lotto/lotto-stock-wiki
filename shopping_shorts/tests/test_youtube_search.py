import pytest
from shopping_shorts import youtube_search


@pytest.fixture(autouse=True)
def isolate_key_state(monkeypatch, tmp_path):
    """모든 테스트에서 실제 data/youtube_key_index.json을 절대 건드리지 않는다."""
    monkeypatch.setattr(youtube_search, "_KEY_STATE_PATH", tmp_path / "youtube_key_index.json")


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEYS", ["fake-key"])

    def fake_get(url, params, timeout):
        assert params["q"] == "floor cleaner"
        assert params["key"] == "fake-key"
        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"items": [
                    {"id": {"videoId": "abc123"},
                     "snippet": {"title": "Floor Cleaner Review",
                                 "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/abc123/mq.jpg"}}}},
                ]}
        return FakeResp()
    monkeypatch.setattr(youtube_search.requests, "get", fake_get)

    results = youtube_search.search("floor cleaner", max_results=10)

    assert results == [{
        "url": "https://www.youtube.com/watch?v=abc123",
        "title": "Floor Cleaner Review",
        "thumbnail": "https://i.ytimg.com/vi/abc123/mq.jpg",
    }]


def test_search_no_keys_raises(monkeypatch):
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEYS", [])
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
        youtube_search.search("x")


def test_search_rotates_on_quota_exhaustion(monkeypatch):
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEYS", ["key1", "key2"])
    calls = []

    class FakeResp:
        def __init__(self, status_code, data=None):
            self.status_code = status_code
            self._data = data or {}
        def raise_for_status(self):
            if self.status_code >= 400:
                err = youtube_search.requests.HTTPError(f"{self.status_code} error")
                err.response = self
                raise err
        def json(self):
            return self._data

    def fake_get(url, params, timeout):
        calls.append(params["key"])
        if params["key"] == "key1":
            return FakeResp(403)
        return FakeResp(200, {"items": [{"id": {"videoId": "x"}, "snippet": {"title": "t", "thumbnails": {"medium": {"url": "u"}}}}]})
    monkeypatch.setattr(youtube_search.requests, "get", fake_get)

    results = youtube_search.search("x")

    assert calls == ["key1", "key2"]
    assert results[0]["url"] == "https://www.youtube.com/watch?v=x"
    # 성공한 키(key2, index 1)가 영구 저장되어 다음 호출은 여기서 시작한다.
    assert youtube_search._load_key_index() == 1


def test_search_all_keys_exhausted_raises(monkeypatch):
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEYS", ["key1", "key2"])

    class FakeResp:
        status_code = 403
        def raise_for_status(self):
            err = youtube_search.requests.HTTPError("403 error")
            err.response = self
            raise err

    monkeypatch.setattr(youtube_search.requests, "get", lambda url, params, timeout: FakeResp())

    with pytest.raises(RuntimeError, match="2"):
        youtube_search.search("x")


def test_search_non_quota_error_raises_immediately(monkeypatch):
    """403/429가 아닌 오류(예: 400 잘못된 요청)는 로테이션하지 않고 즉시 전파한다."""
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEYS", ["key1", "key2"])
    calls = []

    class FakeResp:
        status_code = 400
        def raise_for_status(self):
            err = youtube_search.requests.HTTPError("400 error")
            err.response = self
            raise err

    def fake_get(url, params, timeout):
        calls.append(params["key"])
        return FakeResp()
    monkeypatch.setattr(youtube_search.requests, "get", fake_get)

    with pytest.raises(youtube_search.requests.HTTPError):
        youtube_search.search("x")
    assert calls == ["key1"]
