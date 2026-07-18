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
                        lambda url, source_caption="": items if items is not None else [])
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

    def fake_search(url, source_caption=""):
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
