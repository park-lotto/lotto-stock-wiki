import base64
import types
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store

# 유효한 최소 JPEG(1x1)
_JPG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR"
    "CAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAA"
    "AgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkK"
    "FhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWG"
    "h4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl"
    "5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA"
    "AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYk"
    "NOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOE"
    "hYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk"
    "5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)


def _client(tmp_path, monkeypatch, items=None, limit_reached=False):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "search_similar_videos",
                        lambda url, api_key=None, source_caption="", stats=None, locales=None: items if items is not None else [])
    # imgur 업로드는 네트워크라 목킹 — None 반환 시 서버URL 폴백 경로를 탄다
    monkeypatch.setattr(appmod, "upload_frame", lambda raw: None)
    if limit_reached:
        Store(db).set_setting("lens_month_limit", "0")
    return TestClient(appmod.app), db


def _post_img(c):
    return c.post("/api/lens/search",
                  files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")})


def test_lens_search_returns_filtered_videos(tmp_path, monkeypatch):
    items = [{"platform": "youtube", "url": "https://youtu.be/a", "title": "t", "thumbnail": "x"}]
    c, db = _client(tmp_path, monkeypatch, items=items)
    r = _post_img(c)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["items"] == items and d["count"] == 1
    from datetime import datetime, timezone
    m = datetime.now(timezone.utc).strftime("%Y-%m")
    assert Store(db).lens_month_count(m) == 1


def test_lens_search_forwards_source_caption(tmp_path, monkeypatch):
    """프론트가 보낸 원본 캡션을 lens_discover로 그대로 넘겨야 제목 키워드 매칭이 된다."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "upload_frame", lambda raw: None)
    captured = {}

    def fake_search(url, api_key=None, source_caption="", stats=None, locales=None):
        captured["source_caption"] = source_caption
        return []
    monkeypatch.setattr(appmod, "search_similar_videos", fake_search)
    c = TestClient(appmod.app)
    r = c.post("/api/lens/search",
               files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "다이소 정리박스 꿀템"})
    assert r.status_code == 200
    assert captured["source_caption"] == "다이소 정리박스 꿀템"


def test_lens_search_blocked_when_month_limit_reached(tmp_path, monkeypatch):
    c, db = _client(tmp_path, monkeypatch, items=[], limit_reached=True)
    r = _post_img(c)
    assert r.status_code == 429
    assert r.json()["error_code"] == "lens_limit"


def test_media_url_returns_direct_mp4(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "resolve_media_url",
                        lambda platform, vid: "https://cdn.example/v.mp4?sig=1")
    c = TestClient(appmod.app)
    r = c.get("/api/media?platform=youtube&id=abc123")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "url": "https://cdn.example/v.mp4?sig=1"}


def test_media_url_not_found_returns_ok_false(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "resolve_media_url", lambda platform, vid: "")
    c = TestClient(appmod.app)
    r = c.get("/api/media?platform=tiktok&id=x")
    assert r.status_code == 200
    assert r.json()["ok"] is False


# ── /api/lens/cn : 캡션 키워드 → 샤오홍슈+도우인 병렬 검색 (2026-07-18) ──
def test_lens_cn_merges_and_tags_platforms(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    monkeypatch.setattr(appmod, "cn_search_keyword", lambda cap: "小菜制作")
    monkeypatch.setattr(appmod.xiaohongshu_search, "search",
                        lambda kw, max_results=8: [{"url": "https://xhs/1", "title": "x", "duration": 20, "is_short": True}])
    monkeypatch.setattr(appmod.douyin_search, "search",
                        lambda kw, max_results=8: [{"url": "https://dy/1", "title": "d", "duration": 300, "is_short": False}])
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn", data={"source_caption": "무선 청소기 리뷰"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["count"] == 2
    plats = {i["platform"] for i in d["items"]}
    assert plats == {"xiaohongshu", "douyin"}
    assert d["keyword"] == "小菜制作"                    # Gemini 소재 키워드로 검색
    assert all(i["match"] is None for i in d["items"])   # 소재검색이라 관련도 배지 생략


def test_lens_cn_uses_gemini_topic_keyword(tmp_path, monkeypatch):
    """Gemini 소재 키워드(cn_search_keyword)로 검색하는지 — 앞토큰 직역 아님."""
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    monkeypatch.setattr(appmod, "cn_search_keyword", lambda cap: "玄关收纳")
    seen = {}
    def xhs(kw, max_results=8):
        seen["kw"] = kw
        return [{"url": "https://xhs/1", "title": "玄关鞋柜这样收纳"}]
    monkeypatch.setattr(appmod.xiaohongshu_search, "search", xhs)
    monkeypatch.setattr(appmod.douyin_search, "search", lambda kw, max_results=8: [])
    c = TestClient(appmod.app)
    d = c.post("/api/lens/cn", data={"source_caption": "🔥좁은 현관에 이거 두었더니 끝"}).json()
    assert seen["kw"] == "玄关收纳"
    assert d["keyword"] == "玄关收纳"
    assert d["items"][0]["match"] is None


def test_lens_cn_falls_back_when_gemini_empty(tmp_path, monkeypatch):
    """Gemini가 빈 값이면 앞토큰 직역(translate_keyword)으로 폴백."""
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    monkeypatch.setattr(appmod, "cn_search_keyword", lambda cap: "")        # Gemini 실패
    monkeypatch.setattr(appmod, "translate_keyword", lambda kw: {"zh": "凉拌菜"})
    seen = {}
    def xhs(kw, max_results=8):
        seen["kw"] = kw
        return [{"url": "https://xhs/1", "title": "凉拌菜"}]
    monkeypatch.setattr(appmod.xiaohongshu_search, "search", xhs)
    monkeypatch.setattr(appmod.douyin_search, "search", lambda kw, max_results=8: [])
    c = TestClient(appmod.app)
    d = c.post("/api/lens/cn", data={"source_caption": "새콤달콤 무침 레시피"}).json()
    assert seen["kw"] == "凉拌菜"        # 직역 폴백 사용
    assert d["keyword"] == "凉拌菜"


def test_lens_cn_empty_when_no_caption(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn", data={"source_caption": ""})
    assert r.json()["items"] == [] and r.json()["count"] == 0


def test_lens_cn_empty_when_no_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "APIFY_TOKENS", [])
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn", data={"source_caption": "청소기"})
    assert r.json()["items"] == []


def test_lens_cn_survives_one_actor_error(tmp_path, monkeypatch):
    """한 플랫폼 액터가 죽어도 다른 쪽 결과는 살아야 한다."""
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    monkeypatch.setattr(appmod, "cn_search_keyword", lambda cap: "厨房好物")
    def boom(kw, max_results=8):
        raise RuntimeError("actor down")
    monkeypatch.setattr(appmod.xiaohongshu_search, "search", boom)
    monkeypatch.setattr(appmod.douyin_search, "search",
                        lambda kw, max_results=8: [{"url": "https://dy/2", "title": "d"}])
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn", data={"source_caption": "청소기 리뷰"})
    d = r.json()
    assert d["count"] == 1 and d["items"][0]["platform"] == "douyin"


def test_lens_cn_vision_extract_and_similarity_sort(tmp_path, monkeypatch):
    """장치1(프레임 비전 제품추출)+장치2(유사도 same/similar/no 판정·same 우선 정렬)."""
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    monkeypatch.setattr(appmod, "cn_search_keyword_vision",
                        lambda img, cap: {"product": "리모와 캐리어", "zh": "日默瓦"})
    monkeypatch.setattr(appmod.xiaohongshu_search, "search",
                        lambda kw, max_results=8: [{"url": "https://xhs/1", "title": "RIMOWA 개봉"},
                                                   {"url": "https://xhs/2", "title": "哪吒电影"}])
    monkeypatch.setattr(appmod.douyin_search, "search",
                        lambda kw, max_results=8: [{"url": "https://dy/1", "title": "日默瓦维修"}])
    monkeypatch.setattr(appmod, "judge_same_product",
                        lambda prod, titles: ["same", "no", "similar"])   # items 순서와 정렬
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn", files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "여행 캐리어"})
    d = r.json()
    assert d["product"] == "리모와 캐리어" and d["keyword"] == "日默瓦"
    assert d["items"][0]["url"] == "https://xhs/1"          # same 우선 정렬
    assert d["items"][0]["sim"] == "same" and d["items"][0]["match"] is True
    byurl = {i["url"]: i for i in d["items"]}
    assert byurl["https://xhs/2"]["match"] is False          # no → ⚠️
    assert byurl["https://dy/1"]["sim"] == "similar" and byurl["https://dy/1"]["match"] is None


def test_lens_yt_returns_youtube_items(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "cn_search_keyword_vision",
                        lambda raw, cap: {"product": "물총", "zh": "水枪"})
    fake = [{"url": f"https://youtu.be/v{i}", "title": f"물총 리뷰 {i}",
             "thumbnail": f"https://img/{i}.jpg"} for i in range(3)]
    # 2026-08-16: 렌즈용 호출은 duration/language를 함께 넘긴다(롱폼·외국어 잡음 차단)
    monkeypatch.setattr(appmod, "youtube_search", types.SimpleNamespace(
        search=lambda kw, max_results=40, duration=None, language=None: fake))
    # 2026-08-16: 유튜브도 유사도 채점을 받는다 — 채점이 비면 match는 None 그대로.
    monkeypatch.setattr(appmod, "judge_same_product", lambda p, t: [])
    c = TestClient(appmod.app)
    r = c.post("/api/lens/yt",
               data={"source_caption": "물총 여름 필수템"},
               files={"frame": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["count"] == 3
    assert all(i["platform"] == "youtube" for i in d["items"])
    assert all(i["match"] is None for i in d["items"])
    assert d["keyword"] == "물총"


def test_lens_yt_채점되면_무관한것이_match_False로_표시된다(tmp_path, monkeypatch):
    """유튜브도 '⚠️ 다른주제 숨기기'가 먹혀야 한다(2026-08-16).

    예전엔 match가 무조건 None이라 프론트가 유튜브를 한 개도 못 걸렀다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "cn_search_keyword_vision",
                        lambda raw, cap: {"product": "물총", "zh": "水枪"})
    fake = [{"url": "https://youtu.be/a", "title": "물총 리뷰", "thumbnail": ""},
            {"url": "https://youtu.be/b", "title": "코스피 시황", "thumbnail": ""}]
    monkeypatch.setattr(appmod, "youtube_search", types.SimpleNamespace(
        search=lambda kw, max_results=40, duration=None, language=None: list(fake)))
    monkeypatch.setattr(appmod, "judge_same_product", lambda p, t: ["same", "no"])

    c = TestClient(appmod.app)
    r = c.post("/api/lens/yt", data={"source_caption": "물총"},
               files={"frame": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
    d = r.json()
    byurl = {i["url"]: i for i in d["items"]}
    assert byurl["https://youtu.be/a"]["match"] is True
    assert byurl["https://youtu.be/b"]["match"] is False     # ★프론트가 이걸 거른다
    assert d["items"][0]["url"] == "https://youtu.be/a"      # same 우선 정렬


def test_lens_yt_empty_keyword_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    c = TestClient(appmod.app)
    r = c.post("/api/lens/yt", data={"source_caption": ""})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["count"] == 0


def test_lens_yt_search_failure_returns_empty(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "cn_search_keyword_vision",
                        lambda raw, cap: {"product": "물총", "zh": "水枪"})
    def boom(kw, max_results=40):
        raise RuntimeError("quota exhausted")
    monkeypatch.setattr(appmod, "youtube_search",
                        types.SimpleNamespace(search=boom))
    c = TestClient(appmod.app)
    r = c.post("/api/lens/yt",
               data={"source_caption": "물총"},
               files={"frame": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["count"] == 0


# ── /api/lens/cn/keywords : 프레임 → 중국어 후보 검색어 (2026-07-19) ──
def test_lens_cn_keywords_returns_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "cn_search_candidates",
                        lambda raw, cap, exclude=None: {"product": "감자칩",
                                          "candidates": [{"ko": "공기튀김 감자칩", "zh": "空气炸锅土豆片"}]})
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn/keywords",
               files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "풍선감자"})
    d = r.json()
    assert d["ok"] and d["product"] == "감자칩"
    assert d["candidates"][0]["zh"] == "空气炸锅土豆片"


def test_lens_cn_keywords_forwards_exclude(tmp_path, monkeypatch):
    """🔄 다른 검색어(2026-08-14): 프론트가 보낸 '이미 본 후보'를 비전에 그대로 넘겨야
    같은 3~4개가 또 나오는 복불복이 안 된다."""
    seen = {}

    def fake(raw, cap, exclude=None):
        seen["exclude"] = exclude
        return {"product": "감자칩", "candidates": [{"ko": "회오리감자", "zh": "龙卷风土豆"}]}
    monkeypatch.setattr(appmod, "cn_search_candidates", fake)
    c = TestClient(appmod.app)
    d = c.post("/api/lens/cn/keywords",
               files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "풍선감자",
                     "exclude": "공기튀김 감자칩\n空气炸锅土豆片"}).json()
    assert seen["exclude"] == ["공기튀김 감자칩", "空气炸锅土豆片"]
    assert d["candidates"][0]["zh"] == "龙卷风土豆"


def test_lens_kw_expand_returns_combos(tmp_path, monkeypatch):
    """⌨️ 키워드 직접 넣기(2026-08-14): 한국어 소재어만 넣어도 ko+zh 조합이 나와야 한다."""
    seen = {}

    def fake(kw, n=6, exclude=None):
        seen.update(kw=kw, n=n, exclude=exclude)
        return [{"ko": "시금치 치아바타", "zh": "菠菜恰巴塔"},
                {"ko": "시금치 빵", "zh": "菠菜面包"}]
    monkeypatch.setattr(appmod, "expand_search_keywords", fake)
    c = TestClient(appmod.app)
    d = c.post("/api/lens/kw/expand",
               data={"keyword": "시금치 치아바타", "exclude": "菠菜吐司", "n": 6}).json()
    assert seen["kw"] == "시금치 치아바타" and seen["exclude"] == ["菠菜吐司"]
    assert d["ok"] and d["keyword"] == "시금치 치아바타"
    assert [x["zh"] for x in d["candidates"]] == ["菠菜恰巴塔", "菠菜面包"]


def test_lens_kw_expand_empty_keyword(tmp_path, monkeypatch):
    c = TestClient(appmod.app)
    d = c.post("/api/lens/kw/expand", data={"keyword": "  "}).json()
    assert d["ok"] and d["candidates"] == []


def test_lens_kw_expand_survives_gemini_error(tmp_path, monkeypatch):
    """비전·번역이 죽어도 렌즈 화면이 깨지면 안 된다 — 빈 리스트로 정상 응답."""
    def boom(kw, n=6, exclude=None):
        raise RuntimeError("quota")
    monkeypatch.setattr(appmod, "expand_search_keywords", boom)
    c = TestClient(appmod.app)
    d = c.post("/api/lens/kw/expand", data={"keyword": "시금치"}).json()
    assert d["ok"] and d["candidates"] == []


def test_lens_search_reports_instagram_dropoff(tmp_path, monkeypatch):
    """인스타 편차 계측(2026-08-14): 렌즈 원본 인스타 링크 중 개별 게시물이 아닌 것과
    카드뉴스를 세어 응답 diag에 실어야 '0건'의 원인이 화면에서 갈린다."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "upload_frame", lambda raw: None)
    from shopping_shorts import lens_discover
    raw_matches = [
        {"link": "https://www.instagram.com/reel/AAA111/", "title": "릴"},
        {"link": "https://www.instagram.com/p/BBB222/", "title": "카드뉴스"},
        {"link": "https://www.instagram.com/popular/some-slug/", "title": "모음"},
        {"link": "https://www.instagram.com/someuser/", "title": "프로필"},
    ]
    monkeypatch.setattr(lens_discover, "verify_matches", lambda items, keywords=None: items)
    monkeypatch.setattr(appmod, "search_similar_videos",
                        lambda url, api_key=None, source_caption="", stats=None, locales=None:
                        _run_real(lens_discover, raw_matches, stats))
    c = TestClient(appmod.app)
    d = _post_img(c).json()
    assert d["diag"]["ig_raw"] == 4
    assert d["diag"]["ig_dropped_not_post"] == 2      # /popular/, 프로필
    assert d["diag"]["ig_photo"] == 1                 # /p/
    # 2026-08-16부터 카드뉴스(/p/)는 **서버가 잘라낸다**(사장님 "사진은 자체 커트").
    # 예전엔 통과시키고 프론트 토글이 가리기만 했다 → 이제 릴스 1건만 남는다.
    assert d["diag"]["cut_photo"] == 1
    assert len(d["items"]) == 1


def _run_real(lens_discover, raw_matches, stats):
    """search_similar_videos의 '후처리 루프'만 실제로 태운다(SerpApi 호출 없이).

    ★로케일 1벌로 고정한다 — 2026-08-16부터 기본이 ko+en 2벌이라, 같은 가짜 응답을
      두 번 주면 계측치(ig_raw 등)가 정확히 배로 부풀어 무엇을 세는지 흐려진다.
      이 헬퍼를 쓰는 테스트들은 '인스타 드롭오프 계측'을 보는 것이지 로케일이 아니다."""
    import requests

    class _R:
        status_code = 200
        def json(self): return {"visual_matches": raw_matches}
        def raise_for_status(self): pass
    orig = requests.get
    orig_locales = lens_discover._LENS_LOCALES
    requests.get = lambda *a, **k: _R()
    lens_discover._LENS_LOCALES = (("ko", "kr"),)
    try:
        return lens_discover.search_similar_videos("https://img/x.jpg", api_key="k", stats=stats)
    finally:
        requests.get = orig
        lens_discover._LENS_LOCALES = orig_locales


def test_lens_cn_keywords_empty_without_frame_or_caption(tmp_path, monkeypatch):
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn/keywords", data={"source_caption": ""})
    d = r.json()
    assert d["ok"] and d["candidates"] == []


# ── /api/lens/cn/search : 검색어 1개 → 샤오홍슈+도우인 (2026-07-19) ──
def test_lens_cn_search_merges_platforms(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    seen = {}
    def xhs(kw, max_results=8):
        seen["kw"] = kw
        return [{"url": "https://xhs/1", "title": "空气炸锅土豆片"}]
    monkeypatch.setattr(appmod.xiaohongshu_search, "search", xhs)
    monkeypatch.setattr(appmod.douyin_search, "search",
                        lambda kw, max_results=8: [{"url": "https://dy/1", "title": "土豆片"}])
    c = TestClient(appmod.app)
    d = c.post("/api/lens/cn/search", data={"keyword": "空气炸锅土豆片"}).json()
    assert seen["kw"] == "空气炸锅土豆片"
    assert d["ok"] and d["count"] == 2 and d["keyword"] == "空气炸锅土豆片"
    assert {i["platform"] for i in d["items"]} == {"xiaohongshu", "douyin"}
    assert all(i["match"] is None for i in d["items"])


def test_lens_cn_search_empty_keyword(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    c = TestClient(appmod.app)
    d = c.post("/api/lens/cn/search", data={"keyword": "  "}).json()
    assert d["items"] == [] and d["count"] == 0


def test_lens_cn_search_no_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "APIFY_TOKENS", [])
    c = TestClient(appmod.app)
    d = c.post("/api/lens/cn/search", data={"keyword": "土豆片"}).json()
    assert d["items"] == []


def test_lens_cn_search_survives_one_actor_error(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "APIFY_TOKENS", ["tok"])
    def boom(kw, max_results=8):
        raise RuntimeError("actor down")
    monkeypatch.setattr(appmod.xiaohongshu_search, "search", boom)
    monkeypatch.setattr(appmod.douyin_search, "search",
                        lambda kw, max_results=8: [{"url": "https://dy/2", "title": "d"}])
    c = TestClient(appmod.app)
    d = c.post("/api/lens/cn/search", data={"keyword": "土豆片"}).json()
    assert d["count"] == 1 and d["items"][0]["platform"] == "douyin"


def test_lens_month_limit_scales_with_keys(tmp_path, monkeypatch):
    """렌즈 월 한도 = 키 개수 × 250(계정당). 설정 override 있으면 그 값.

    ★250은 실측값이다(2026-08-16, SerpApi account API로 직접 확인: 두 키 다 플랜 250).
      예전 상수 100은 실제와 달라, 카운터가 200에 닿으면 **아직 300회가 남았는데도**
      렌즈를 막았다."""
    per = appmod._LENS_MONTH_LIMIT_PER_KEY
    assert per == 250, "실측 플랜과 어긋나면 멀쩡한데 막힌다"
    s = Store(str(tmp_path / "t.db"))
    import shopping_shorts.config as cfg
    monkeypatch.setattr(cfg, "SERPAPI_KEYS", ["k1"])
    assert appmod._lens_month_limit(s) == per
    monkeypatch.setattr(cfg, "SERPAPI_KEYS", ["k1", "k2"])
    assert appmod._lens_month_limit(s) == per * 2       # 2번째 키 넣으면 자동 2배
    monkeypatch.setattr(cfg, "SERPAPI_KEYS", [])
    assert appmod._lens_month_limit(s) == per           # 키 0개여도 최소 1키분
    s.set_setting("lens_month_limit", "50")
    assert appmod._lens_month_limit(s) == 50            # 설정 override 우선


# ── /api/lens/search 유사도 채점 (2026-08-21) ────────────────────────────
# 왜: 샤오홍슈·도우인(/api/lens/cn)과 유튜브(/api/lens/yt)엔 judge_same_product가
#     붙어 있는데 **메인 렌즈에만 빠져 있었다**. 그래서 렌즈 본 결과는 옛 문자열
#     매칭(_title_matches: 2자 토큰 부분포함)에만 의존했고, 프론트의
#     '⚠️ 다른주제 숨기기'가 거의 못 걸렀다. 같은 함수를 그대로 쓴다(0순위-B).

def test_lens_search_채점되면_무관한것이_match_False로_표시된다(tmp_path, monkeypatch):
    """메인 렌즈도 AI 유사도 채점을 받는다 — ⚠️다른주제 배지가 정확해진다."""
    items = [
        {"platform": "instagram", "url": "https://www.instagram.com/reel/AAA/",
         "title": "물총 리뷰", "match": None},
        {"platform": "instagram", "url": "https://www.instagram.com/reel/BBB/",
         "title": "코스피 시황", "match": None},
    ]
    c, _ = _client(tmp_path, monkeypatch, items=items)
    monkeypatch.setattr(appmod, "judge_same_product", lambda p, t: ["same", "no"])
    d = c.post("/api/lens/search", files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "물총"}).json()
    byurl = {i["url"]: i for i in d["items"]}
    assert byurl["https://www.instagram.com/reel/AAA/"]["match"] is True
    assert byurl["https://www.instagram.com/reel/BBB/"]["match"] is False   # ★프론트가 거른다
    assert byurl["https://www.instagram.com/reel/AAA/"]["sim"] == "same"


def test_lens_search_관련도순_정렬되고_인스타우선은_유지된다(tmp_path, monkeypatch):
    """정렬 키 2개: ①관련도(same→similar→no) ②같은 관련도면 인스타 먼저.

    기존 동작(인스타 우선)을 깨지 않으면서 관련도를 **위 순위**로 얹는다."""
    items = [
        {"platform": "instagram", "url": "https://www.instagram.com/reel/NO/",
         "title": "무관", "match": None},
        {"platform": "youtube", "url": "https://youtu.be/SAME", "title": "딱 그것", "match": None},
        {"platform": "instagram", "url": "https://www.instagram.com/reel/SAME/",
         "title": "딱 그것 인스타", "match": None},
    ]
    c, _ = _client(tmp_path, monkeypatch, items=items)
    monkeypatch.setattr(appmod, "judge_same_product", lambda p, t: ["no", "same", "same"])
    d = c.post("/api/lens/search", files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "물총"}).json()
    urls = [i["url"] for i in d["items"]]
    # same 둘이 앞, 그 안에서 인스타가 유튜브보다 먼저, no는 맨 뒤
    assert urls == ["https://www.instagram.com/reel/SAME/",
                    "https://youtu.be/SAME",
                    "https://www.instagram.com/reel/NO/"]


def test_lens_search_채점실패해도_결과는_그대로_나온다(tmp_path, monkeypatch):
    """채점이 빈 배열(키 소진·모델 실패)이면 기존 동작 그대로 — 결과를 죽이지 않는다."""
    items = [
        {"platform": "youtube", "url": "https://youtu.be/x", "title": "a", "match": None},
        {"platform": "instagram", "url": "https://www.instagram.com/reel/CCC/",
         "title": "b", "match": None},
    ]
    c, _ = _client(tmp_path, monkeypatch, items=items)
    monkeypatch.setattr(appmod, "judge_same_product", lambda p, t: [])
    d = c.post("/api/lens/search", files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "물총"}).json()
    assert d["count"] == 2
    assert d["items"][0]["platform"] == "instagram"      # 폴백 = 종전 인스타 우선 정렬


def test_lens_search_채점이_예외를_던져도_검색은_산다(tmp_path, monkeypatch):
    """채점은 부가기능이다 — 터져도 렌즈 결과를 통째로 죽이면 안 된다."""
    items = [{"platform": "instagram", "url": "https://www.instagram.com/reel/DDD/",
              "title": "a", "match": None}]
    c, _ = _client(tmp_path, monkeypatch, items=items)

    def _boom(p, t):
        raise RuntimeError("gemini down")
    monkeypatch.setattr(appmod, "judge_same_product", _boom)
    d = c.post("/api/lens/search", files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_caption": "물총"}).json()
    assert d["ok"] is True and d["count"] == 1


def test_lens_search_캡션없으면_채점을_아예_안_부른다(tmp_path, monkeypatch):
    """기준 제품이 없으면 채점은 무의미하다 — 헛돈(Gemini 호출)을 쓰지 않는다."""
    called = []
    items = [{"platform": "instagram", "url": "https://www.instagram.com/reel/EEE/",
              "title": "a", "match": None}]
    c, _ = _client(tmp_path, monkeypatch, items=items)
    monkeypatch.setattr(appmod, "judge_same_product",
                        lambda p, t: called.append(1) or ["same"])
    d = c.post("/api/lens/search",
               files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")}).json()   # 캡션 없음
    assert d["ok"] is True
    assert called == []          # ★한 번도 안 불렀다


# ── 검색 국가 고르기 API (2026-08-22) ────────────────────────────────────
# 사장님: "김밥 렌즈를 해외꺼까지 돌릴 거 없잖아" — 국내 소재는 한국만 돌려 SerpApi를 아낀다.

def test_lens_locales_목록을_서버가_알려준다(tmp_path, monkeypatch):
    """프론트가 칩을 그릴 목록. ★서버 설정을 그대로 노출한다(하드코딩 금지)."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    c = TestClient(appmod.app)
    d = c.get("/api/lens/locales").json()
    assert d["ok"] is True and d["locales"]
    keys = [x["key"] for x in d["locales"]]
    assert keys == [f"{hl}:{cc}" for hl, cc in appmod.lens_discover._LENS_LOCALES]
    assert all(x["label"] for x in d["locales"])          # 이름이 비면 칩이 빈칸이 된다


def test_lens_search_고른_나라만_서버로_전달된다(tmp_path, monkeypatch):
    """폼의 locales가 search_similar_videos까지 도달하는가(배선 확인)."""
    got = {}

    def _spy(url, api_key=None, source_caption="", stats=None, locales=None):
        got["locales"] = locales
        return []
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "upload_frame", lambda raw: "https://img/x.jpg")
    monkeypatch.setattr(appmod, "search_similar_videos", _spy)
    c = TestClient(appmod.app)
    r = c.post("/api/lens/search", files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"locales": "ko:kr"})
    assert r.status_code == 200
    assert got["locales"] == [("ko", "kr")]


def test_lens_search_locales_없으면_빈목록_전달_전체가_돈다(tmp_path, monkeypatch):
    """옛 화면(locales를 안 보냄)도 그대로 돌아야 한다 — 회귀 0."""
    got = {}

    def _spy(url, api_key=None, source_caption="", stats=None, locales=None):
        got["locales"] = locales
        return []
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "upload_frame", lambda raw: "https://img/x.jpg")
    monkeypatch.setattr(appmod, "search_similar_videos", _spy)
    c = TestClient(appmod.app)
    c.post("/api/lens/search", files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")})
    assert got["locales"] == []       # 빈 목록 → lens_discover가 전체로 폴백한다


def test_parse_lens_locales_잡값을_걸러낸다():
    """콜론 없는 값·빈 칸·공백은 버린다. 판정(유효성)은 lens_discover가 한다."""
    assert appmod._parse_lens_locales("ko:kr, ja:jp") == [("ko", "kr"), ("ja", "jp")]
    assert appmod._parse_lens_locales("") == []
    assert appmod._parse_lens_locales("garbage,,:,ko:") == []
    assert appmod._parse_lens_locales("  ko:kr  ") == [("ko", "kr")]


# ── 검색어 소재 보강 (2026-08-22 사장님 "썸네일 캡션 대본을 빠르게 스캔해서") ──
# 왜: 검색어가 **썸네일 1장만** 보고 만들어져 제품을 잘못 짚었다(실측 3건 중 2건:
#     다이소 바닥보수제→"스틱청소기", 과탄산소다→"이염방지시트").
#     캡션은 reel_history엔 거의 비어 있고(300건 중 1건) source_enrichment에 1,260건
#     있는데 **아무도 안 읽고 있었다**. 대본(script_extracts)도 마찬가지.

def test_lens_소재수집_캡션이_비면_DB에서_채운다(tmp_path, monkeypatch):
    """프론트가 빈 캡션을 보내도 서버가 DB(source_enrichment)에서 찾아 쓴다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.upsert_enrichment("https://www.instagram.com/reel/AAA/", "instagram",
                         {"caption": "다이소 가면 이거 꼭 사오세요 바닥 찍힘 복구"},
                         "ok", "2026-08-22T00:00:00")
    got = appmod._lens_source_text("https://www.instagram.com/reel/AAA/", "", store=st)
    assert "다이소" in got and "바닥 찍힘" in got


def test_lens_소재수집_대본이_있으면_함께_쓴다(tmp_path, monkeypatch):
    """★대본에만 있는 제품명이 검색어를 살린다(실측: '과탄산소다'는 대본에만 있었다)."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("BBB", {"full_text": "흰 양말 누렇게 된 거 과탄산소다 한 스푼이면 됩니다"})
    got = appmod._lens_source_text("https://www.instagram.com/reel/BBB/", "", store=st)
    assert "과탄산소다" in got


def test_lens_소재수집_프론트캡션이_있으면_그것도_쓴다(tmp_path, monkeypatch):
    """프론트가 준 캡션을 버리지 않는다 — DB에 없을 때 유일한 단서다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    got = appmod._lens_source_text("https://x/reel/CCC/", "프론트가 준 캡션", store=st)
    assert "프론트가 준 캡션" in got


def test_lens_소재수집_아무것도_없으면_빈문자(tmp_path, monkeypatch):
    """DB에도 없고 프론트도 안 주면 빈 문자열 — 옛 동작(썸네일만) 그대로."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    assert appmod._lens_source_text("https://x/reel/NONE/", "", store=st) == ""


def test_lens_소재수집_길이를_자른다(tmp_path, monkeypatch):
    """대본이 길면 프롬프트가 비대해진다 — 상한을 둔다(비용·지연)."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("LONG", {"full_text": "가" * 5000})
    got = appmod._lens_source_text("https://x/reel/LONG/", "", store=st)
    assert 0 < len(got) <= appmod._LENS_SRC_MAX


def test_lens_소재수집_DB오류여도_죽지_않는다(tmp_path, monkeypatch):
    """보강은 부가기능이다 — DB가 터져도 렌즈 검색은 살아야 한다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))

    class _Boom:
        def get_enrichment(self, *a, **k): raise RuntimeError("db down")
        def get_script(self, *a, **k): raise RuntimeError("db down")
    assert appmod._lens_source_text("https://x/reel/X/", "원본캡션", store=_Boom()) == "원본캡션"


# ── 제품명(source_brief.product) 합류 (2026-09-06 사장님 "자막을 다 보고 제품명에
#    가까운 내용을 검색어로 뽑아야 한다" / 목적 = 샤오홍슈에서 원본 영상 찾기) ──
# 왜: 추출기는 **자막·화면까지 다 보고** 제품명을 정해 source_brief.product에 넣는데
#     렌즈는 full_text만 읽어 그 값을 한 번도 안 봤다. 서버 실측(2026-09-06):
#     09월 추출분 1,970건 중 1,969건(99%)에 product가 있고, **나레이션이 0자인 280건
#     중 279건**도 product는 채워져 있다 — 무자막 영상을 살리는 유일한 재료다.

def test_lens_소재수집_제품명을_쓴다(tmp_path, monkeypatch):
    """★source_brief.product가 소재에 들어간다 — 이게 빠지면 렌즈가 썸네일만 보고 찍는다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("PRD", {"full_text": "반년째 쓰는데 아직도 새거같은 이유는",
                           "source_brief": {"product": "휴대용 실리콘 롤클리너",
                                            "core": "물로 씻어 반영구 재사용"}})
    got = appmod._lens_source_text("https://x/reel/PRD/", "", store=st)
    assert "휴대용 실리콘 롤클리너" in got
    assert "물로 씻어 반영구 재사용" in got


def test_lens_소재수집_제품명이_맨앞이다(tmp_path, monkeypatch):
    """★맨 앞이어야 한다 — 프롬프트가 소재를 **앞에서부터** 자르므로, 뒤에 있으면
    긴 대본에서 제품명이 통째로 잘려나간다(2026-09-06 실측: 잘린 112자에 핵심어 4개)."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("HEAD", {"full_text": "안녕하세요 " * 400,      # 상한을 훌쩍 넘기는 대본
                            "source_brief": {"product": "실리콘 롤클리너"}})
    got = appmod._lens_source_text("https://x/reel/HEAD/", "", store=st)
    assert got.startswith("[제품] 실리콘 롤클리너")
    assert "실리콘 롤클리너" in got            # 길이 상한에 잘려나가지 않았다


def test_lens_소재수집_나레이션이_0자여도_제품명은_남는다(tmp_path, monkeypatch):
    """★무자막·무음성 영상(서버 실측 280건)에서 유일한 재료다. 예전엔 빈 문자열이었다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("MUTE", {"full_text": "", "source_brief": {"product": "스팀 알밤"}})
    got = appmod._lens_source_text("https://x/reel/MUTE/", "", store=st)
    assert "스팀 알밤" in got


def test_lens_소재수집_옛추출본은_그대로_지나간다(tmp_path, monkeypatch):
    """source_brief가 없는 옛 추출본(07월분 204건)에서 터지지 않는다 — full_text만 쓴다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("OLD", {"full_text": "옛날 대본"})
    got = appmod._lens_source_text("https://x/reel/OLD/", "", store=st)
    assert got == "옛날 대본"


def test_lens_소재수집_source_brief가_문자열이어도_안죽는다(tmp_path, monkeypatch):
    """★source_brief는 dict인데 옛 데이터엔 문자열로 들어간 것이 있다(app.py:19736 주석).
    dict가 아니면 조용히 건너뛴다 — 여기서 터지면 렌즈가 통째로 죽는다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("STR", {"full_text": "본문", "source_brief": "문자열로 들어간 옛 데이터"})
    got = appmod._lens_source_text("https://x/reel/STR/", "", store=st)
    assert got == "본문"


def test_렌즈_검색어_길이상한이_캐시키와_같다():
    """★캐시키와 프롬프트가 **같은 상수**를 써야 한다(0순위-B).
    다르면 서로 다른 소재가 한 캐시칸을 공유해 오답이 TTL 동안 굳는다
    (memory `reference_캐시키_불일치함정`)."""
    from shopping_shorts import video_analysis as va
    long_src = "가" * 5000
    k1 = va._frame_cache_key(b"x", long_src[:va._LENS_PROMPT_SRC_MAX])
    k2 = va._frame_cache_key(b"x", long_src)
    assert k1 == k2          # 상한을 넘는 부분은 키에 영향을 주지 않는다


def test_렌즈_검색어_온도가_0이다():
    """★같은 영상을 다시 눌러도 같은 답이 나와야 한다(2026-09-06 사장님
    "이번에는 완전 다른거 나왔어"). 실측: 기본 온도로 같은 입력 5회에 5회 전부
    다른 제품(버터커터기/에어팟케이스/미니커터/미니칼/실패)이 나왔다.
    ★문자열 검색이 아니라 **실제 config 객체**를 잡아 값을 본다."""
    import types as _t
    from shopping_shorts import video_analysis as va
    seen = {}

    class _Resp:
        text = '{"product":"x","candidates":[{"ko":"a","zh":"b"}]}'

    class _Models:
        def generate_content(self, **kw):
            seen["cfg"] = kw.get("config")
            return _Resp()

    class _Client:
        models = _Models()

    va_keys = va.SHORTS_GEMINI_KEYS
    try:
        va.SHORTS_GEMINI_KEYS = ["k"]
        import shopping_shorts.comment_gen as cg
        _orig = cg._next_live_key_and_idx
        cg._next_live_key_and_idx = lambda: ("k", 0)
        _origc = va._client_for_key
        va._client_for_key = lambda key: _Client()
        va.cn_search_candidates(b"jpegbytes", "소재")
    finally:
        va.SHORTS_GEMINI_KEYS = va_keys
        cg._next_live_key_and_idx = _orig
        va._client_for_key = _origc
    assert seen.get("cfg") is not None, "generate_content가 불리지 않았다"
    assert getattr(seen["cfg"], "temperature", None) == 0


# ── has_source 신호 + 📝 대본 분석 후 찾기 (2026-09-06 사장님 "대본분석후찾기 버튼 만들고") ──
# 렌즈는 DB에 **이미 있는** 소재만 읽는다(대본추출을 하지 않는다). 소재가 0자면 검색어는
# 썸네일 1장만 보고 지어져 매번 달라지고, 틀려도 정답처럼 보인다. 서버가 그 사실을
# has_source로 알려주고 프론트가 버튼을 띄운다. ★판정은 서버 한 곳(0순위-B) —
# 프론트가 캡션 길이로 따로 재면 서버가 DB에서 채운 소재를 몰라 반드시 어긋난다.

def test_렌즈_소재가_없으면_has_source_거짓(tmp_path, monkeypatch):
    """소재 0자 = 썸네일만 보고 찍은 것 → 프론트가 '대본 분석 후 찾기'를 띄운다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "cn_search_candidates",
                        lambda raw, src, exclude=None: {"product": "", "candidates": []})
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn/keywords",
               files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_url": "https://x/reel/NOSRC/"})
    assert r.json()["has_source"] is False


def test_렌즈_대본이_있으면_has_source_참(tmp_path, monkeypatch):
    """대본추출을 돌린 영상은 소재가 있으므로 버튼을 띄우지 않는다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    st = Store(str(tmp_path / "t.db"))
    st.save_script("HASSRC", {"full_text": "옷 먼지 떼는 실리콘 돌돌이입니다",
                              "source_brief": {"product": "휴대용 실리콘 롤클리너"}})
    monkeypatch.setattr(appmod, "cn_search_candidates",
                        lambda raw, src, exclude=None: {"product": "x", "candidates": []})
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn/keywords",
               files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_url": "https://x/reel/HASSRC/"})
    assert r.json()["has_source"] is True


def test_렌즈_비전이_터져도_has_source가_NameError를_안낸다(tmp_path, monkeypatch):
    """★src를 try 안에서만 만들면 예외 시 has_source가 NameError로 500이 된다."""
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))

    def _boom(*a, **k):
        raise RuntimeError("db down")
    # ★소재 만들기 자체를 터뜨려야 한다 — cn_search_candidates를 터뜨리면 그 **앞줄**에서
    #   src가 이미 채워져 NameError가 안 난다(사보타주로 확인: 가짜 단언이었다).
    monkeypatch.setattr(appmod, "_lens_source_text", _boom)
    c = TestClient(appmod.app)
    r = c.post("/api/lens/cn/keywords",
               files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")},
               data={"source_url": "https://x/reel/BOOM/"})
    assert r.status_code == 200
    assert r.json()["ok"] is True and r.json()["candidates"] == []
