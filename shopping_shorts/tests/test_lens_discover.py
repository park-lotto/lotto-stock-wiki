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
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))

    out = lens_discover.search_similar_videos("https://ex.com/frame.jpg")

    platforms = [i["platform"] for i in out]
    assert platforms == ["youtube", "tiktok", "instagram", "xiaohongshu", "douyin"]
    # is_photo(카드뉴스 후보) 추가 2026-07-30 — 프론트 '🎬 영상만' 토글이 이 키를 본다.
    # is_short/duration 추가 2026-08-16 — 롱폼 서버컷용. 길이를 모르면 None·숏폼 취급.
    assert out[0] == {"platform": "youtube", "url": "https://www.youtube.com/watch?v=abc",
                      "title": "yt", "thumbnail": "t1", "match": None, "is_photo": False,
                      "is_short": True, "duration": None}


def test_youtu_be_and_xhslink_and_iesdouyin(monkeypatch):
    matches = [
        {"link": "https://youtu.be/abc", "title": "y", "thumbnail": "a", "source": "YouTube"},
        {"link": "https://xhslink.com/xxx", "title": "x", "thumbnail": "b", "source": "RED"},
        {"link": "https://www.iesdouyin.com/share/video/1", "title": "d", "thumbnail": "c", "source": "抖音"},
    ]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
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
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
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
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    urls = [i["url"] for i in out]
    # /p/(카드뉴스)는 2026-08-16부터 **서버가 잘라낸다**(사장님 "사진은 자체 커트").
    # 예전엔 통과시키고 프론트 토글로 가리기만 했다.
    assert urls == ["https://www.instagram.com/reel/DkAbc123/"]


def test_requests_type_visual_matches(monkeypatch):
    """google_lens는 요리·제품 프레임 같은 이미지엔 ai_overview만 주고 visual_matches를
    생략한다(2026-07-14 라이브 실측: type 없으면 0개, type=visual_matches면 60개).
    항상 type=visual_matches를 명시해야 결과가 온다 — 이 파라미터 누락이 '유사영상
    못 찾음' 버그의 원인이었다."""
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    captured = {}

    seen = []

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        seen.append((params or {}).get("hl"))
        return _fake_response([])
    monkeypatch.setattr(lens_discover.requests, "get", fake_get)

    lens_discover.search_similar_videos("https://ex.com/f.jpg")
    # type=visual_matches를 넣으면 안 된다 — 그 별도 엔드포인트는 많은 프레임에서 "no results"를
    # 준다(2026-07-14 실측: type 있으면 0개, 없는 all모드면 59~60개). 기본 all모드로 부른다.
    assert "type" not in captured["params"]
    # 로케일 — 2026-08-16부터 ko/kr + en/us 두 벌을 돈다(사장님 "다른 프로그램은
    # 자막없는 원본을 가져온다"). ko만 쓰면 한국어 자막판만 올라온다.
    # 실측 A/B: 같은 이미지 9건 → 27건, 늘어난 18건은 전부 비한글 제목.
    # ※이 응답은 **빈 결과**라 ko에서 _MAX_ATTEMPTS(3)만큼 재시도하며 호출예산
    #   (_MAX_CALLS_PER_SEARCH=3)을 다 쓴다 → en·zh는 건너뛴다. 그게 상한의 목적이다
    #   (2026-08-16 "무조건 한번클릭에 3회"). 여기선 ko로 시작하는 것과 상한만 본다.
    assert seen[0] == "ko"
    assert len(seen) <= lens_discover._MAX_CALLS_PER_SEARCH, f"상한 초과: {seen}"
    # 결과가 정상일 때 로케일 3벌을 도는지는 test_lens_merge_locales.py가 본다.


def test_retries_when_lens_returns_no_results_then_succeeds(monkeypatch):
    """google_lens는 갓 호스팅된 이미지에 첫 호출 때 'hasn't returned any results'로
    빈 응답을 주고, 잠시 후 재호출하면 결과를 준다(2026-07-14 실측: 같은 URL이 0개→60개).
    이 일시적 빈 결과에 대해 재시도해야 사용자가 매번 '못 찾음'을 안 본다."""
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.time, "sleep", lambda s: None)  # 테스트 대기 제거
    # 이 테스트가 보는 건 '재시도'다 — 로케일 2벌(2026-08-16)이 섞이면 호출 수가
    # 배로 늘어 무엇을 세는지 흐려진다. 로케일 1벌로 고정하고 재시도만 검증한다.
    monkeypatch.setattr(lens_discover, "_LENS_LOCALES", (("ko", "kr"),))
    calls = {"n": 0}

    class R:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    def flaky_get(url, params=None, timeout=None):
        if "oembed" in url:            # oEmbed 실검증(2026-08-03)은 렌즈 재시도 횟수와 무관
            return R({})
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


def test_rotates_to_next_key_when_first_exhausted(monkeypatch):
    """첫 키가 월 한도 소진(429)이면 두 번째 키로 넘어가 결과를 받는다."""
    matches = [{"link": "https://www.youtube.com/watch?v=abc", "title": "y",
                "thumbnail": "t1", "source": "YouTube"}]
    used = []

    class R:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload
        def raise_for_status(self):
            if self.status_code >= 400:
                import requests as _rq
                raise _rq.HTTPError("boom")
        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        used.append(params["api_key"])
        if params["api_key"] == "k1":
            return R(429, {"error": "Your account has run out of searches."})
        return R(200, {"visual_matches": matches})

    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["k1", "k2"])
    # 이 테스트가 보는 건 '키 로테이션'이다 — 로케일 2벌이면 k1,k2가 두 번씩
    # 찍혀 무엇을 세는지 흐려진다. 로케일 1벌로 고정한다(2026-08-16).
    monkeypatch.setattr(lens_discover, "_LENS_LOCALES", (("ko", "kr"),))
    monkeypatch.setattr(lens_discover.requests, "get", fake_get)

    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert [i["platform"] for i in out] == ["youtube"]
    assert used == ["k1", "k2"]   # 첫 키 소진 → 둘째 키로 전환


def test_all_keys_exhausted_returns_empty(monkeypatch):
    """모든 키가 소진이면 빈 결과(크래시 없이)."""
    class R:
        status_code = 429
        def raise_for_status(self): pass
        def json(self): return {"error": "ran out of searches"}
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["k1", "k2"])
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: R())
    assert lens_discover.search_similar_videos("https://ex.com/f.jpg") == []


def test_no_key_returns_empty(monkeypatch):
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", [])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "")
    assert lens_discover.search_similar_videos("https://ex.com/f.jpg") == []


def test_request_failure_returns_empty(monkeypatch):
    import requests as _rq
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
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
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg", source_caption="다이소 신상 정리박스 꿀템")
    assert out[0]["match"] is True


def test_match_false_when_no_keyword_overlap(monkeypatch):
    matches = [{"link": "https://www.youtube.com/watch?v=abc",
                "title": "감자 크로켓 레시피", "thumbnail": "t1", "source": "YouTube"}]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg", source_caption="다이소 신상 정리박스 꿀템")
    assert out[0]["match"] is False


def test_match_none_when_no_source_caption(monkeypatch):
    matches = [{"link": "https://www.youtube.com/watch?v=abc",
                "title": "아무 제목", "thumbnail": "t1", "source": "YouTube"}]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert out[0]["match"] is None
    out2 = lens_discover.search_similar_videos("https://ex.com/f.jpg", source_caption="   ")
    assert out2[0]["match"] is None


# ── 카드뉴스(사진 게시물) 표시 — 사장님 제보 2026-07-30 "인스타 카드뉴스가 많다" ──
# 렌즈 응답엔 동영상 여부 필드가 없고 인스타 실조회는 Apify 유료 → URL 경로가 유일한 공짜 신호.
def test_is_photo_post_flags_instagram_p_only():
    from shopping_shorts.lens_discover import is_photo_post
    assert is_photo_post("instagram", "https://www.instagram.com/p/DAbc123/") is True
    assert is_photo_post("instagram", "https://instagram.com/p/Xy_9-z/?igsh=abc") is True
    # /reel·/reels·/tv = 영상 확정 → 가리지 않는다
    assert is_photo_post("instagram", "https://www.instagram.com/reel/DAbc123/") is False
    assert is_photo_post("instagram", "https://www.instagram.com/reels/DAbc123/") is False
    assert is_photo_post("instagram", "https://www.instagram.com/tv/DAbc123/") is False
    # 인스타 외 플랫폼은 판정하지 않는다(틱톡 사진첩은 _is_watchable이 입구에서 거른다)
    assert is_photo_post("youtube", "https://www.youtube.com/shorts/abc") is False
    assert is_photo_post("tiktok", "https://www.tiktok.com/@a/video/123") is False
    assert is_photo_post("instagram", "") is False


def test_search_similar_videos_cuts_photo_posts(monkeypatch):
    """카드뉴스(/p/)는 **결과에서 아예 빠진다**(2026-08-16 사장님 "사진은 자체 커트").

    예전엔 is_photo=True로 실어 보내고 프론트 토글이 가리기만 했다 — 개수엔 계속
    잡히고 토글을 끄면 다시 나왔다. 이제 서버가 잘라 남은 항목은 전부 is_photo=False."""
    from shopping_shorts import lens_discover

    class _R:
        status_code = 200
        def json(self):
            return {"visual_matches": [
                {"link": "https://www.instagram.com/p/AAA111/", "title": "카드뉴스", "thumbnail": "t1"},
                {"link": "https://www.instagram.com/reel/BBB222/", "title": "릴스", "thumbnail": "t2"},
            ]}
        def raise_for_status(self):
            return None

    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _R())
    st = {}
    out = lens_discover.search_similar_videos("http://img/x.jpg", api_key="k", stats=st)
    assert [i["url"] for i in out] == ["https://www.instagram.com/reel/BBB222/"]
    assert [i["is_photo"] for i in out] == [False]
    assert st["cut_photo"] == 1
