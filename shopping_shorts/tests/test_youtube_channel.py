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
