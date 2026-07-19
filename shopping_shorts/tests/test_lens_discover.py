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
    assert out[0] == {"platform": "youtube", "url": "https://www.youtube.com/watch?v=abc", "title": "yt", "thumbnail": "t1", "match": None}


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


def test_excludes_tiktok_discover_search_pages(monkeypatch):
    """틱톡 discover/tag/search URL은 개별 영상이 아니라 검색·모음 페이지라 제외한다
    (2026-07-14 실측: 렌즈가 tiktok.com/discover/키워드 형태를 섞어 반환 — 재생·매칭
    의미 없음). @user/video/숫자 형태의 개별 영상만 통과."""
    matches = [
        {"link": "https://www.tiktok.com/discover/일본-고구마-탕후루", "title": "d", "thumbnail": "t", "source": "TikTok"},
        {"link": "https://www.tiktok.com/@zihyuncook/video/7564364411620625685", "title": "v", "thumbnail": "t", "source": "TikTok"},
        {"link": "https://www.tiktok.com/tag/potato", "title": "tag", "thumbnail": "t", "source": "TikTok"},
        {"link": "https://www.tiktok.com/search?q=x", "title": "s", "thumbnail": "t", "source": "TikTok"},
    ]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert len(out) == 1
    assert out[0]["url"].endswith("/video/7564364411620625685")


def test_excludes_instagram_non_permalink_pages(monkeypatch):
    """렌즈는 개별 릴이 아닌 인스타 SEO·모음 페이지(/popular/{제목슬러그}·/explore·프로필)를
    섞어 반환한다(2026-07-19 실사고: 렌즈 즐겨찾기로 담긴 instagram.com/popular/바나나-아침-식사/
    가 매칭 단계에서 'Apify 해석 실패'로 배치 전체를 죽임). /p·/reel·/reels·/tv + 코드의
    개별 permalink만 통과시킨다."""
    matches = [
        {"link": "https://www.instagram.com/popular/바나나-아침-식사/", "title": "p", "thumbnail": "t", "source": "Instagram"},
        {"link": "https://www.instagram.com/reel/DkAbc123/", "title": "r", "thumbnail": "t", "source": "Instagram"},
        {"link": "https://www.instagram.com/explore/tags/breakfast/", "title": "e", "thumbnail": "t", "source": "Instagram"},
        {"link": "https://www.instagram.com/some_user/", "title": "prof", "thumbnail": "t", "source": "Instagram"},
        {"link": "https://www.instagram.com/p/CyXyZ00/", "title": "post", "thumbnail": "t", "source": "Instagram"},
    ]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    urls = [i["url"] for i in out]
    assert urls == ["https://www.instagram.com/reel/DkAbc123/", "https://www.instagram.com/p/CyXyZ00/"]


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
    # type=visual_matches를 넣으면 안 된다 — 그 별도 엔드포인트는 많은 프레임에서 "no results"를
    # 준다(2026-07-14 실측: type 있으면 0개, 없는 all모드면 59~60개). 기본 all모드로 부른다.
    assert "type" not in captured["params"]
    # 로케일(hl=ko&country=kr) 필수 — 없으면 한국어 콘텐츠 매칭이 약하다(실측).
    assert captured["params"]["hl"] == "ko"
    assert captured["params"]["country"] == "kr"


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


def test_upload_to_imgur_returns_public_link(monkeypatch):
    """캡처 바이트 → imgur 익명 업로드 → 공개 URL. Google Lens가 우리서버 URL은
    갓 호스팅돼 인덱싱 지연으로 못 읽지만(0개), imgur는 상시 크롤링돼 즉시 매칭된다
    (2026-07-14 실측: 같은 프레임 우리서버=0, imgur=59). 실패 시 None."""
    captured = {}

    class R:
        status_code = 200
        def json(self): return {"success": True, "data": {"link": "https://i.imgur.com/abc.jpeg"}}

    def fake_post(url, headers=None, files=None, timeout=None):
        captured["url"] = url
        captured["auth"] = headers.get("Authorization", "")
        return R()
    monkeypatch.setattr(lens_discover.requests, "post", fake_post)

    link = lens_discover.upload_to_imgur(b"\xff\xd8\xff\x00jpegbytes")
    assert link == "https://i.imgur.com/abc.jpeg"
    assert "imgur.com" in captured["url"]
    assert captured["auth"].startswith("Client-ID ")


def test_upload_to_imgur_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise lens_discover.requests.RequestException("net")
    monkeypatch.setattr(lens_discover.requests, "post", boom)
    assert lens_discover.upload_to_imgur(b"x") is None


# ── imgbb 업로드(2026-07-14) ──────────────────────
# imgur이 신규 전용 Client-ID 발급을 막아놔서(정책변경, 실측·크로스검증 완료) 전용키
# 발급이 열려있는 imgbb를 1순위로 승격. 실측: 프레시 이미지 기준 imgur과 동일하게
# 즉시 인덱싱(대기 0초 60개 매칭, imgur=60/imgbb=60 동시비교).

def test_upload_to_imgbb_returns_public_url(monkeypatch):
    captured = {}

    class R:
        status_code = 200
        def json(self): return {"success": True, "data": {"url": "https://i.ibb.co/abc/x.jpg"}}

    def fake_post(url, data=None, files=None, timeout=None):
        captured["url"] = url
        captured["key"] = data.get("key")
        return R()
    monkeypatch.setattr(lens_discover.requests, "post", fake_post)

    link = lens_discover.upload_to_imgbb(b"\xff\xd8\xff\x00jpegbytes", api_key="fakekey")
    assert link == "https://i.ibb.co/abc/x.jpg"
    assert "imgbb.com" in captured["url"]
    assert captured["key"] == "fakekey"


def test_upload_to_imgbb_no_key_returns_none(monkeypatch):
    monkeypatch.setattr(lens_discover, "_IMGBB_API_KEY", "")
    assert lens_discover.upload_to_imgbb(b"x") is None


def test_upload_to_imgbb_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise lens_discover.requests.RequestException("net")
    monkeypatch.setattr(lens_discover.requests, "post", boom)
    assert lens_discover.upload_to_imgbb(b"x", api_key="fakekey") is None


def test_upload_frame_prefers_imgbb_over_imgur(monkeypatch):
    calls = []
    monkeypatch.setattr(lens_discover, "upload_to_imgbb", lambda raw: calls.append("imgbb") or "https://i.ibb.co/x.jpg")
    monkeypatch.setattr(lens_discover, "upload_to_imgur", lambda raw: calls.append("imgur") or "https://i.imgur.com/x.jpg")
    assert lens_discover.upload_frame(b"x") == "https://i.ibb.co/x.jpg"
    assert calls == ["imgbb"]   # imgbb 성공하면 imgur은 아예 호출 안 함


def test_upload_frame_falls_back_to_imgur_when_imgbb_fails(monkeypatch):
    monkeypatch.setattr(lens_discover, "upload_to_imgbb", lambda raw: None)
    monkeypatch.setattr(lens_discover, "upload_to_imgur", lambda raw: "https://i.imgur.com/x.jpg")
    assert lens_discover.upload_frame(b"x") == "https://i.imgur.com/x.jpg"


def test_upload_frame_none_when_both_fail(monkeypatch):
    monkeypatch.setattr(lens_discover, "upload_to_imgbb", lambda raw: None)
    monkeypatch.setattr(lens_discover, "upload_to_imgur", lambda raw: None)
    assert lens_discover.upload_frame(b"x") is None


def test_no_key_returns_empty(monkeypatch):
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "")
    assert lens_discover.search_similar_videos("https://ex.com/f.jpg") == []


def test_request_failure_returns_empty(monkeypatch):
    import requests as _rq
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    def boom(*a, **k): raise _rq.RequestException("net")
    monkeypatch.setattr(lens_discover.requests, "get", boom)
    assert lens_discover.search_similar_videos("https://ex.com/f.jpg") == []


# ── 제목 키워드 후처리 필터(2026-07-14) ──────────────────────
# 렌즈는 시각 유사도만 보기 때문에 장르는 같지만 다른 주제인 결과가 섞인다(실측).
# 소스 캡션 키워드가 결과 제목에 있는지로 match 필드를 매겨 프론트가 표시만 하게 한다
# (하드 필터는 교차언어 플랫폼에서 회수율을 떨어뜨리므로 하지 않는다).

def test_match_true_when_title_contains_source_keyword(monkeypatch):
    matches = [{"link": "https://www.youtube.com/watch?v=abc",
                "title": "다이소 꿀템 정리박스 추천", "thumbnail": "t1", "source": "YouTube"}]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg", source_caption="다이소 신상 정리박스 꿀템")
    assert out[0]["match"] is True


def test_match_false_when_no_keyword_overlap(monkeypatch):
    matches = [{"link": "https://www.youtube.com/watch?v=abc",
                "title": "감자 크로켓 레시피", "thumbnail": "t1", "source": "YouTube"}]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg", source_caption="다이소 신상 정리박스 꿀템")
    assert out[0]["match"] is False


def test_match_none_when_no_source_caption(monkeypatch):
    matches = [{"link": "https://www.youtube.com/watch?v=abc",
                "title": "아무 제목", "thumbnail": "t1", "source": "YouTube"}]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert out[0]["match"] is None
    out2 = lens_discover.search_similar_videos("https://ex.com/f.jpg", source_caption="   ")
    assert out2[0]["match"] is None
