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
                        lambda url, source_caption="", stats=None: items if items is not None else [])
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

    def fake_search(url, source_caption="", stats=None):
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
    monkeypatch.setattr(appmod, "youtube_search",
                        types.SimpleNamespace(search=lambda kw, max_results=40: fake))
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
                        lambda url, source_caption="", stats=None:
                        _run_real(lens_discover, raw_matches, stats))
    c = TestClient(appmod.app)
    d = _post_img(c).json()
    assert d["diag"]["ig_raw"] == 4
    assert d["diag"]["ig_dropped_not_post"] == 2      # /popular/, 프로필
    assert d["diag"]["ig_photo"] == 1                 # /p/
    assert len(d["items"]) == 2                       # reel + /p/(가리기는 프론트 토글)


def _run_real(lens_discover, raw_matches, stats):
    """search_similar_videos의 '후처리 루프'만 실제로 태운다(SerpApi 호출 없이)."""
    import requests

    class _R:
        status_code = 200
        def json(self): return {"visual_matches": raw_matches}
        def raise_for_status(self): pass
    orig = requests.get
    requests.get = lambda *a, **k: _R()
    try:
        return lens_discover.search_similar_videos("https://img/x.jpg", api_key="k", stats=stats)
    finally:
        requests.get = orig


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
    """렌즈 월 한도 = 키 개수 × 100(무료 계정당). 설정 override 있으면 그 값."""
    s = Store(str(tmp_path / "t.db"))
    import shopping_shorts.config as cfg
    monkeypatch.setattr(cfg, "SERPAPI_KEYS", ["k1"])
    assert appmod._lens_month_limit(s) == 100
    monkeypatch.setattr(cfg, "SERPAPI_KEYS", ["k1", "k2"])
    assert appmod._lens_month_limit(s) == 200          # 2번째 키 넣으면 자동 200
    monkeypatch.setattr(cfg, "SERPAPI_KEYS", [])
    assert appmod._lens_month_limit(s) == 100          # 키 0개여도 최소 100
    s.set_setting("lens_month_limit", "50")
    assert appmod._lens_month_limit(s) == 50            # 설정 override 우선
