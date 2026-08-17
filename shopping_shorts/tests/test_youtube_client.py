from shopping_shorts import youtube_client as yc


def test_parse_search_and_stats(monkeypatch):
    # search.list 응답(검색) + videos.list 응답(통계)을 mock
    search_resp = {"items": [
        {"id": {"videoId": "vid1"},
         "snippet": {"channelId": "ch1", "channelTitle": "살림TV",
                     "title": "오이 보관법", "description": "꿀팁",
                     "publishedAt": "2026-07-12T00:00:00Z",
                     "thumbnails": {"high": {"url": "http://t/vid1.jpg"}}}}
    ]}
    stats_resp = {"items": [
        {"id": "vid1", "statistics": {"viewCount": "10000", "likeCount": "500", "commentCount": "40"}}
    ]}

    calls = {"n": 0}
    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        class R:
            status_code = 200
            def json(self_inner):
                return search_resp if "search" in url else stats_resp
        return R()
    monkeypatch.setattr(yc.requests, "get", fake_get)

    items = yc.search_shorts(["살림꿀팁"], "2026-07-11T00:00:00Z", max_per_kw=20, token="KEY")
    assert len(items) == 1
    it = items[0]
    assert it["video_id"] == "vid1"
    assert it["channel_title"] == "살림TV"
    assert it["views"] == 10000 and it["likes"] == 500 and it["comments"] == 40
    assert it["thumbnail"] == "https://i.ytimg.com/vi/vid1/oardefault.jpg"  # 세로 쇼츠 썸네일


def test_key_rotation_on_quota_403(monkeypatch):
    # 첫 키는 search.list에서 403(쿼터 초과) → 두번째 키로 재시도해서 성공해야 한다.
    search_resp = {"items": [
        {"id": {"videoId": "vid1"},
         "snippet": {"channelId": "ch1", "channelTitle": "살림TV",
                     "title": "오이 보관법", "description": "꿀팁",
                     "publishedAt": "2026-07-12T00:00:00Z",
                     "thumbnails": {"high": {"url": "http://t/vid1.jpg"}}}}
    ]}
    stats_resp = {"items": [
        {"id": "vid1", "statistics": {"viewCount": "10000", "likeCount": "500", "commentCount": "40"}}
    ]}

    calls = {"search_tokens": [], "stats_tokens": []}

    def fake_get(url, params=None, timeout=None):
        key = params["key"]

        class R:
            def __init__(self, status_code, body):
                self.status_code = status_code
                self._body = body

            def json(self_inner):
                return self_inner._body

        if "search" in url:
            calls["search_tokens"].append(key)
            if key == "KEY1":
                return R(403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})
            return R(200, search_resp)
        calls["stats_tokens"].append(key)
        return R(200, stats_resp)

    monkeypatch.setattr(yc.requests, "get", fake_get)
    # ★search_shorts의 키 선택은 keyroute를 거친다(2026-08-17 BYOK). keyroute._owner_keys가
    #   읽는 곳은 config.YOUTUBE_API_KEYS라 모듈 전역만 갈아끼우면 안 먹는다.
    #   yc.YOUTUBE_API_KEYS도 같이 두는 이유: _first_ok 등 다른 경로는 아직 모듈 전역을 본다.
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["KEY1", "KEY2"])
    monkeypatch.setattr(yc.config, "YOUTUBE_API_KEYS", ["KEY1", "KEY2"])

    items = yc.search_shorts(["살림꿀팁"], "2026-07-11T00:00:00Z", max_per_kw=20)
    assert len(items) == 1
    assert items[0]["video_id"] == "vid1"
    assert calls["search_tokens"] == ["KEY1", "KEY2"]   # KEY1 403 이후 KEY2로 재시도
    assert calls["stats_tokens"] == ["KEY2"]            # 통계도 성공한 키(KEY2)로 조회


def test_key_rotation_explicit_token_no_rotation(monkeypatch):
    # 호출부가 명시적으로 token=을 넘기면(단일 토큰) 로테이션 없이 그 토큰만 사용.
    def fake_get(url, params=None, timeout=None):
        class R:
            status_code = 403
            def json(self_inner):
                return {}
        return R()
    monkeypatch.setattr(yc.requests, "get", fake_get)
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["KEY1", "KEY2"])

    items = yc.search_shorts(["살림꿀팁"], "2026-07-11T00:00:00Z", token="ONLY")
    assert items == []
