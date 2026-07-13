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
    assert it["thumbnail"] == "http://t/vid1.jpg"
