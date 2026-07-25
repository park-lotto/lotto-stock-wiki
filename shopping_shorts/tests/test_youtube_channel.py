from shopping_shorts import youtube_client as yc


def test_parse_duration_secs():
    assert yc._parse_duration_secs("PT59S") == 59
    assert yc._parse_duration_secs("PT1M") == 60
    assert yc._parse_duration_secs("PT1M1S") == 61
    assert yc._parse_duration_secs("PT2M") == 120
    assert yc._parse_duration_secs("PT1H2M3S") == 3723
    assert yc._parse_duration_secs("") is None
    assert yc._parse_duration_secs(None) is None


def test_resolve_channel_url_direct_no_api(monkeypatch):
    # /channel/UC.. URL은 정규식 직접 파싱 → requests 호출 0회, uploads=UU+id[2:]
    def boom(*a, **k):
        raise AssertionError("requests.get 호출되면 안 됨")
    monkeypatch.setattr(yc.requests, "get", boom)

    cid, uploads = yc._resolve_channel("https://www.youtube.com/channel/UCabc123def")
    assert cid == "UCabc123def"
    assert uploads == "UUabc123def"


def test_resolve_channel_handle_via_api(monkeypatch):
    # @handle → channels.list?forHandle → id + uploads 플레이리스트
    resp = {"items": [{"id": "UCxyz",
                       "contentDetails": {"relatedPlaylists": {"uploads": "UUxyz"}}}]}

    def fake_get(url, params=None, timeout=None):
        assert "channels" in url and params.get("forHandle") == "@salim"
        class R:
            status_code = 200
            def raise_for_status(self_inner):
                pass
            def json(self_inner):
                return resp
        return R()
    monkeypatch.setattr(yc.requests, "get", fake_get)
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["KEY1"])

    cid, uploads = yc._resolve_channel("@salim")
    assert cid == "UCxyz" and uploads == "UUxyz"


def test_resolve_channel_unresolvable(monkeypatch):
    # 해석 실패(빈 items) → (None, None), 예외 안 던짐
    def fake_get(url, params=None, timeout=None):
        class R:
            status_code = 200
            def raise_for_status(self_inner):
                pass
            def json(self_inner):
                return {"items": []}
        return R()
    monkeypatch.setattr(yc.requests, "get", fake_get)
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["KEY1"])

    assert yc._resolve_channel("@ghost") == (None, None)


def _mk_get(playlist_resp, videos_resp, seen):
    def fake_get(url, params=None, timeout=None):
        seen.append(url)
        class R:
            status_code = 200
            def raise_for_status(self_inner):   # 실 _first_ok가 호출 → no-op
                pass
            def json(self_inner):
                if "playlistItems" in url:
                    return playlist_resp
                return videos_resp
        return R()
    return fake_get


def test_fetch_channel_shorts_schema_and_60s_filter(monkeypatch):
    # _resolve_channel은 캐시 콜백이 값을 주면 호출 안 됨
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["KEY1"])
    playlist_resp = {"items": [
        {"contentDetails": {"videoId": "short1", "videoPublishedAt": "2026-07-24T00:00:00Z"}},
        {"contentDetails": {"videoId": "long1", "videoPublishedAt": "2026-07-24T00:00:00Z"}},
    ]}
    videos_resp = {"items": [
        {"id": "short1",
         "snippet": {"channelId": "UCx", "channelTitle": "살림TV", "title": "오이보관",
                     "description": "d", "publishedAt": "2026-07-24T00:00:00Z",
                     "thumbnails": {"high": {"url": "http://t/short1.jpg"}}},
         "contentDetails": {"duration": "PT45S"},
         "statistics": {"viewCount": "5000", "likeCount": "200", "commentCount": "15"}},
        {"id": "long1",
         "snippet": {"channelId": "UCx", "channelTitle": "살림TV", "title": "긴영상",
                     "description": "d", "publishedAt": "2026-07-24T00:00:00Z",
                     "thumbnails": {"high": {"url": "http://t/long1.jpg"}}},
         "contentDetails": {"duration": "PT3M"},
         "statistics": {"viewCount": "9000", "likeCount": "10", "commentCount": "1"}},
    ]}
    seen = []
    monkeypatch.setattr(yc.requests, "get", _mk_get(playlist_resp, videos_resp, seen))

    puts = []
    got = yc.fetch_channel_shorts(
        "@salim",
        cache_get=lambda s: ("UCx", "UUx"),                 # 캐시 히트 → resolve 스킵
        cache_put=lambda s, c, u: puts.append((s, c, u)))

    assert len(got) == 1                                    # 3분짜리 long1 제외
    it = got[0]
    assert it["video_id"] == "short1"
    assert it["channel_id"] == "UCx" and it["channel_title"] == "살림TV"
    assert it["views"] == 5000 and it["likes"] == 200 and it["comments"] == 15
    assert it["thumbnail"] == "https://i.ytimg.com/vi/short1/oardefault.jpg"  # 세로 쇼츠 썸네일
    assert it["published_at"] == "2026-07-24T00:00:00Z"
    # 캐시 히트라 channels.list(해석) 호출 없음
    assert not any("channels" in u for u in seen)
    assert puts == []                                       # 히트면 put 안 함


def test_fetch_channel_shorts_resolves_and_caches(monkeypatch):
    # 캐시 미스 → _resolve_channel 호출 → cache_put 기록
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["KEY1"])   # _first_ok가 키 1개는 있어야 요청 시도
    monkeypatch.setattr(yc, "_resolve_channel", lambda seed: ("UCy", "UUy"))
    playlist_resp = {"items": [
        {"contentDetails": {"videoId": "s1", "videoPublishedAt": "2026-07-24T00:00:00Z"}}]}
    videos_resp = {"items": [
        {"id": "s1",
         "snippet": {"channelId": "UCy", "channelTitle": "채널", "title": "t",
                     "description": "", "publishedAt": "2026-07-24T00:00:00Z",
                     "thumbnails": {"high": {"url": "u"}}},
         "contentDetails": {"duration": "PT30S"},
         "statistics": {"viewCount": "100", "likeCount": "2", "commentCount": "0"}}]}
    monkeypatch.setattr(yc.requests, "get", _mk_get(playlist_resp, videos_resp, []))

    puts = []
    got = yc.fetch_channel_shorts("@new", cache_get=lambda s: None,
                                  cache_put=lambda s, c, u: puts.append((s, c, u)))
    assert len(got) == 1 and got[0]["video_id"] == "s1"
    assert puts == [("@new", "UCy", "UUy")]                 # 해석 결과 캐시에 저장


def test_fetch_channel_shorts_unresolvable_returns_empty(monkeypatch):
    monkeypatch.setattr(yc, "_resolve_channel", lambda seed: (None, None))
    got = yc.fetch_channel_shorts("@ghost", cache_get=lambda s: None,
                                  cache_put=lambda s, c, u: None)
    assert got == []
