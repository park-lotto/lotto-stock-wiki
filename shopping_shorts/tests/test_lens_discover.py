from shopping_shorts import lens_discover


def _fake_response(matches):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"visual_matches": matches}
    return R()


def test_filters_to_supported_video_platforms(monkeypatch):
    # 핀터레스트는 2026-08-29부터 지원 플랫폼이다(사장님 "핀터레스트 검색결과도 노출").
    # 이 테스트의 requests 몽키패치는 핀 페이지 실조회까지 막으므로 판정불가 →
    # 남되 is_photo=True(기본 가림)여야 한다. 영상확정·이미지컷은 아래 전용 테스트에서.
    matches = [
        {"link": "https://www.youtube.com/watch?v=abc", "title": "yt", "thumbnail": "t1", "source": "YouTube"},
        {"link": "https://www.tiktok.com/@u/video/1", "title": "tt", "thumbnail": "t2", "source": "TikTok"},
        {"link": "https://www.instagram.com/reel/xyz/", "title": "ig", "thumbnail": "t3", "source": "Instagram"},
        {"link": "https://www.xiaohongshu.com/explore/aaa", "title": "xhs", "thumbnail": "t4", "source": "小红书"},
        {"link": "https://www.douyin.com/video/999", "title": "dy", "thumbnail": "t5", "source": "抖音"},
        {"link": "https://en.wikipedia.org/wiki/X", "title": "wiki", "thumbnail": "t6", "source": "Wikipedia"},
        {"link": "https://www.pinterest.com/pin/18295942229438860/", "title": "pin", "thumbnail": "t7", "source": "Pinterest"},
    ]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get", lambda *a, **k: _fake_response(matches))

    out = lens_discover.search_similar_videos("https://ex.com/frame.jpg")

    platforms = [i["platform"] for i in out]
    assert platforms == ["youtube", "tiktok", "instagram", "xiaohongshu", "douyin",
                         "pinterest"]
    pin = out[-1]
    assert pin["is_photo"] is True          # 판정불가 → 기본 가림(삭제 아님)
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


# ── 검색 국가 고르기 (2026-08-22 사장님 "김밥 렌즈를 해외까지 돌릴 거 없잖아") ──
# 왜: 지금은 로케일 4벌이 **무조건** 다 나간다. 국내 소재인 걸 아는데도 SerpApi를
#     4회 쓴다. 부르는 쪽이 국가를 고르면 1회로 줄어든다(잔량 4배).
# ★ 고른 국가만 도는가 / 안 고르면 종전대로 전부 도는가 — 둘 다 고정한다.

def _locale_spy(monkeypatch):
    """_lens_call이 어떤 로케일로 불렸는지 기록한다."""
    seen = []
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")

    def _spy(image_url, keys, hl, country, timeout, budget=None, dead=None):
        seen.append((hl, country))
        if budget is not None:
            budget[0] -= 1
        return []
    monkeypatch.setattr(lens_discover, "_lens_call", _spy)
    return seen


def test_locales_인자가_없으면_종전대로_전부_돈다(monkeypatch):
    """기존 호출부는 한 글자도 안 고쳐도 그대로 돌아야 한다(회귀 0)."""
    seen = _locale_spy(monkeypatch)
    lens_discover.search_similar_videos("https://ex.com/f.jpg")
    assert seen == list(lens_discover._LENS_LOCALES)


def test_locales_로_고른_나라만_돈다(monkeypatch):
    """★한국만 고르면 SerpApi가 1회만 나간다 — 이게 이 기능의 전부다."""
    seen = _locale_spy(monkeypatch)
    lens_discover.search_similar_videos("https://ex.com/f.jpg", locales=[("ko", "kr")])
    assert seen == [("ko", "kr")]


def test_locales_두_나라를_고르면_그_둘만_돈다(monkeypatch):
    """★설정에 실제로 있는 로케일로만 고른다 — ja:jp는 서버 env에만 있어서
    로컬(_LENS_LOCALES = ko·en·zh 3벌)에서 쓰면 필터에 걸려 테스트가 환경을 탄다."""
    seen = _locale_spy(monkeypatch)
    pick = list(lens_discover._LENS_LOCALES)[:2]
    assert len(pick) == 2, "설정 로케일이 2개 미만이면 이 테스트는 의미가 없다"
    lens_discover.search_similar_videos("https://ex.com/f.jpg", locales=pick)
    assert seen == pick


def test_locales_가_비면_전부_돈다(monkeypatch):
    """★빈 목록으로 렌즈가 빈손이 되는 사고를 막는다 — 0개면 종전 전체로 되돌린다.

    프론트가 칩을 전부 끈 채 보내거나, 옛 화면이 빈 값을 보낼 수 있다."""
    seen = _locale_spy(monkeypatch)
    lens_discover.search_similar_videos("https://ex.com/f.jpg", locales=[])
    assert seen == list(lens_discover._LENS_LOCALES)


def test_locales_모르는_나라는_걸러낸다(monkeypatch):
    """설정에 없는 로케일은 무시한다 — 아무 값이나 SerpApi로 흘려보내지 않는다."""
    seen = _locale_spy(monkeypatch)
    lens_discover.search_similar_videos(
        "https://ex.com/f.jpg", locales=[("ko", "kr"), ("xx", "yy")])
    assert seen == [("ko", "kr")]


def test_locales_전부_모르는_값이면_전부_돈다(monkeypatch):
    """걸러낸 결과가 0개여도 빈손이 되면 안 된다(위 빈 목록과 같은 안전핀)."""
    seen = _locale_spy(monkeypatch)
    lens_discover.search_similar_videos("https://ex.com/f.jpg", locales=[("xx", "yy")])
    assert seen == list(lens_discover._LENS_LOCALES)


def test_한_나라만_고르면_예산도_한_번만_쓴다(monkeypatch):
    """비용 절감이 목적이다 — 고른 수만큼만 SerpApi를 쓴다."""
    stats = {}
    _locale_spy(monkeypatch)
    lens_discover.search_similar_videos("https://ex.com/f.jpg",
                                        locales=[("ko", "kr")], stats=stats)
    assert stats["serpapi_calls"] == 1


# ── 핀터레스트 노출 (2026-08-29 사장님 "핀터레스트 검색결과도 노출해줘 / 숏폼영상만") ──
# 렌즈가 주는 핀 링크는 대부분 이미지 핀인데 응답에 영상 여부가 없다 → 핀 페이지의
# JSON-LD VideoObject(pinterest_crawl.pin_video_info)를 실조회해 **영상 핀만** 남긴다.
# 실측(2026-08-29): 영상 핀 2/2 VideoObject 있음 / 이미지 핀 4/4 없음.

def _pin_search(monkeypatch, pin_links, info_fn):
    """핀 링크들로 SerpApi 응답을 꾸미고 pin_video_info만 갈아끼워 검색 전체를 돌린다."""
    matches = [{"link": u, "title": "p", "thumbnail": "t", "source": "Pinterest"}
               for u in pin_links]
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["fake"])
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "fake")
    monkeypatch.setattr(lens_discover.requests, "get",
                        lambda *a, **k: _fake_response(matches))
    monkeypatch.setattr(lens_discover.pinterest_crawl, "pin_video_info", info_fn)
    stats = {}
    out = lens_discover.search_similar_videos("https://ex.com/f.jpg", stats=stats)
    return out, stats


def test_핀터레스트_영상핀은_남고_mp4가_실린다(monkeypatch):
    def info(url, timeout=None):
        return {"video_url": "https://v1.pinimg.com/videos/mc/720p/a.mp4",
                "duration": 15.0, "thumbnail": "https://i.pinimg.com/t.jpg",
                "title": "진짜 제목", "description": ""}
    out, stats = _pin_search(monkeypatch,
                             ["https://www.pinterest.com/pin/18295942229438860/"], info)
    assert len(out) == 1
    pin = out[0]
    assert pin["platform"] == "pinterest"
    # play_url = 프론트 기존 인라인 재생 경로(/api/video 프록시)가 읽는 필드
    assert pin["play_url"].endswith("a.mp4")
    assert pin["duration"] == 15.0 and pin["is_short"] is True
    assert pin["title"] == "진짜 제목"       # 보이는 것 = 열리는 것(oEmbed 검증과 같은 원칙)
    assert stats["pin_raw"] == 1 and stats["pin_video"] == 1 and stats["pin_dropped"] == 0


def test_핀터레스트_이미지핀은_서버가_잘라낸다(monkeypatch):
    """사장님 요구가 '숏폼영상만'이다 — 이미지 확정 핀은 응답에서 아예 뺀다
    (2026-08-16 '사진·롱폼 자체 커트'와 같은 원칙)."""
    out, stats = _pin_search(monkeypatch,
                             ["https://www.pinterest.com/pin/1084452785302525968/"],
                             lambda url, timeout=None: None)
    assert out == []
    assert stats["pin_raw"] == 1 and stats["pin_dropped"] == 1


def test_핀터레스트_롱폼은_잘라낸다(monkeypatch):
    def info(url, timeout=None):
        return {"video_url": "https://v1.pinimg.com/x.mp4", "duration": 999.0,
                "thumbnail": "", "title": "", "description": ""}
    out, _ = _pin_search(monkeypatch,
                         ["https://www.pinterest.com/pin/18295942229438860/"], info)
    assert out == []


def test_핀터레스트_판정불가는_지우지_않고_기본가림(monkeypatch):
    """네트워크 실패 = 이미지 확정이 아니다. 자르면 회수율이 깎인다 →
    is_photo=True로만 표시(프론트 '🎬 영상만' 토글 기본 켜짐이라 가려지고, 끄면 보인다)."""
    def boom(url, timeout=None):
        raise RuntimeError("핀 페이지 HTTP 503")
    out, stats = _pin_search(monkeypatch,
                             ["https://www.pinterest.com/pin/18295942229438860/"], boom)
    assert len(out) == 1
    assert out[0]["is_photo"] is True
    assert "play_url" not in out[0]
    assert stats["pin_dropped"] == 0


def test_핀터레스트_실조회_상한밖은_기본가림(monkeypatch):
    """핀 페이지는 1.3MB HTML(실측)이라 개수 뚜껑(_PIN_VERIFY_MAX)을 씌운다.
    상한 밖은 실조회 없이 판정불가 취급 — 지우지 않는다."""
    calls = []

    def info(url, timeout=None):
        calls.append(url)
        return {"video_url": "https://v1.pinimg.com/x.mp4", "duration": 10.0,
                "thumbnail": "", "title": "", "description": ""}
    n = lens_discover._PIN_VERIFY_MAX
    links = [f"https://www.pinterest.com/pin/1000000000000{i:04d}/" for i in range(n + 3)]
    out, stats = _pin_search(monkeypatch, links, info)
    assert len(calls) == n                      # 상한만큼만 실조회
    assert len(out) == n + 3                    # 상한 밖도 안 지운다
    assert sum(1 for i in out if i.get("is_photo")) == 3   # 상한 밖 = 기본 가림


def test_핀터레스트_개별핀만_통과한다():
    ok = lens_discover._is_watchable
    assert ok("pinterest", "https://www.pinterest.com/pin/123456/") is True
    assert ok("pinterest", "https://kr.pinterest.com/pin/slug-name--123456/") is True
    assert ok("pinterest", "https://www.pinterest.com/search/pins/?q=x") is False
    assert ok("pinterest", "https://www.pinterest.com/username/board-name/") is False


def test_핀터레스트_중복은_핀id로_뭉갠다():
    """같은 핀이 kr./www.·슬러그 유무로 제각각 온다(실측) — netloc+path 키로는
    전부 달라 같은 카드가 여러 장 뜬다."""
    a = lens_discover._dedup_key("https://kr.pinterest.com/pin/18295942229438860/")
    b = lens_discover._dedup_key(
        "https://www.pinterest.com/pin/stylish-gadgets--18295942229438860/")
    assert a == b == "pinterest.com/pin/18295942229438860"
