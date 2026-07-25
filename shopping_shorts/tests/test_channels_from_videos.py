from shopping_shorts import youtube_client as yc


def test_video_id_from_url_variants():
    f = yc._video_id_from_url
    assert f("https://www.youtube.com/watch?v=abc123DEF_-") == "abc123DEF_-"
    assert f("https://youtu.be/abc123DEF_-") == "abc123DEF_-"
    assert f("https://www.youtube.com/shorts/abc123DEF_-") == "abc123DEF_-"
    assert f("https://www.youtube.com/embed/abc123DEF_-") == "abc123DEF_-"
    assert f("https://www.youtube.com/watch?v=abc123DEF_-&t=5s") == "abc123DEF_-"
    assert f("https://instagram.com/reel/xyz") is None
    assert f("") is None
    assert f(None) is None


def _mk_get(videos_resp, seen):
    def fake_get(url, params=None, timeout=None):
        seen.append(params.get("id"))
        class R:
            status_code = 200
            def raise_for_status(self_inner):
                pass
            def json(self_inner):
                return videos_resp
        return R()
    return fake_get


def test_channels_from_video_urls_dedupes_and_skips_nonyoutube(monkeypatch):
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["KEY1"])
    videos_resp = {"items": [
        {"id": "v1", "snippet": {"channelId": "UCaaa", "channelTitle": "로지홈"}},
        {"id": "v2", "snippet": {"channelId": "UCaaa", "channelTitle": "로지홈"}},   # 같은 채널
        {"id": "v3", "snippet": {"channelId": "UCbbb", "channelTitle": "생활GIFTBOX"}},
    ]}
    seen = []
    monkeypatch.setattr(yc.requests, "get", _mk_get(videos_resp, seen))

    out = yc.channels_from_video_urls([
        "https://www.youtube.com/watch?v=v1",
        "https://youtu.be/v2",
        "https://www.youtube.com/shorts/v3",
        "https://instagram.com/reel/nope",     # 비유튜브 → 스킵
        "https://www.youtube.com/watch?v=v1",  # 중복 URL
    ])

    # 채널 2개(UCaaa 1번만), 첫 등장 순서 보존
    assert [c["channel_id"] for c in out] == ["UCaaa", "UCbbb"]
    assert out[0]["channel_title"] == "로지홈"
    assert out[0]["channel_url"] == "https://www.youtube.com/channel/UCaaa"
    assert out[1]["channel_url"] == "https://www.youtube.com/channel/UCbbb"
    # 유튜브 video_id 3개만 조회(중복 v1 제거)
    assert seen == ["v1,v2,v3"]


def test_channels_from_video_urls_empty_when_no_youtube(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("비유튜브만이면 API 호출 없어야 함")
    monkeypatch.setattr(yc.requests, "get", boom)
    assert yc.channels_from_video_urls(["https://instagram.com/reel/x"]) == []
    assert yc.channels_from_video_urls([]) == []
