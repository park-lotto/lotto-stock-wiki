from shopping_shorts import lens_discover


def _fake_response(matches):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"visual_matches": matches}
    return R()


def test_filters_to_five_video_platforms(monkeypatch):
    matches = [
        {"link": "https://www.youtube.com/watch?v=abc", "title": "yt", "thumbnail": "t1", "source": "YouTube"},
        {"link": "https://www.tiktok.com/@u/video/1", "title": "tt", "thumbnail": "t2", "source": "TikTok"},
        {"link": "https://www.instagram.com/reel/xyz/", "title": "ig", "thumbnail": "t3", "source": "Instagram"},
        {"link": "https://www.xiaohongshu.com/explore/aaa", "title": "xhs", "thumbnail": "t4", "source": "小红书"},
        {"link": "https://www.douyin.com/video/999", "title": "dy", "thumbnail": "t5", "source": "抖音"},
        {"link": "https://en.wikipedia.org/wiki/X", "title": "wiki", "thumbnail": "t6", "source": "Wikipedia"},
        {"link": "https://www.pinterest.com/pin/1", "title": "pin", "thumbnail": "t7", "source": "Pinterest"},
    ]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))

    out = lens_discover.search_similar_videos("https://ex.com/frame.jpg")

    platforms = [i["platform"] for i in out]
    assert platforms == ["youtube", "tiktok", "instagram", "xiaohongshu", "douyin"]
    assert out[0] == {"platform": "youtube", "url": "https://www.youtube.com/watch?v=abc", "title": "yt", "thumbnail": "t1"}


def test_youtu_be_and_xhslink_and_iesdouyin(monkeypatch):
    matches = [
        {"link": "https://youtu.be/abc", "title": "y", "thumbnail": "a", "source": "YouTube"},
        {"link": "https://xhslink.com/xxx", "title": "x", "thumbnail": "b", "source": "RED"},
        {"link": "https://www.iesdouyin.com/share/video/1", "title": "d", "thumbnail": "c", "source": "抖音"},
    ]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert [i["platform"] for i in out] == ["youtube", "xiaohongshu", "douyin"]


def test_requests_type_visual_matches(monkeypatch):
    """google_lens는 요리·제품 프레임 같은 이미지엔 ai_overview만 주고 visual_matches를
    생략한다(2026-07-14 라이브 실측: type 없으면 0개, type=visual_matches면 60개).
    항상 type=visual_matches를 명시해야 결과가 온다 — 이 파라미터 누락이 '유사영상
    못 찾음' 버그의 원인이었다."""
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _fake_response([])
    monkeypatch.setattr(lens_discover.requests, "get", fake_get)

    lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert captured["params"]["type"] == "visual_matches"


def test_retries_when_lens_returns_no_results_then_succeeds(monkeypatch):
    """google_lens는 갓 호스팅된 이미지에 첫 호출 때 'hasn't returned any results'로
    빈 응답을 주고, 잠시 후 재호출하면 결과를 준다(2026-07-14 실측: 같은 URL이 0개→60개).
    이 일시적 빈 결과에 대해 재시도해야 사용자가 매번 '못 찾음'을 안 본다."""
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.time, "sleep", lambda s: None)  # 테스트 대기 제거
    calls = {"n": 0}

    class R:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    def flaky_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return R({"error": "Google Lens hasn't returned any results for this query."})
        return R({"visual_matches": [
            {"link": "https://youtu.be/a", "title": "y", "thumbnail": "t", "source": "YouTube"}]})
    monkeypatch.setattr(lens_discover.requests, "get", flaky_get)

    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert calls["n"] == 2                      # 첫 빈 응답 후 재시도함
    assert len(out) == 1 and out[0]["platform"] == "youtube"


def test_no_key_returns_empty(monkeypatch):
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "")
    assert lens_discover.search_similar_videos("https://ex.com/f.jpg") == []


def test_request_failure_returns_empty(monkeypatch):
    import requests as _rq
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    def boom(*a, **k): raise _rq.RequestException("net")
    monkeypatch.setattr(lens_discover.requests, "get", boom)
    assert lens_discover.search_similar_videos("https://ex.com/f.jpg") == []
