import pytest
import requests
from fastapi.testclient import TestClient
from shopping_shorts.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


import shopping_shorts.app as app_module
from fastapi.testclient import TestClient


def _client_with_auth(monkeypatch, password="secret123"):
    monkeypatch.setattr(app_module, "DASH_PASS", password)
    monkeypatch.setattr(app_module, "DASH_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_AUTH_ON", True)
    return TestClient(app_module.app)


def test_auth_off_by_default(monkeypatch):
    """DASH_PASS 비어있으면(로컬 개발) 인증 없이 통과."""
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    client = TestClient(app_module.app)
    r = client.get("/api/reference")
    assert r.status_code == 200


def test_unauthenticated_api_returns_401(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.get("/api/reference")
    assert r.status_code == 401


def test_unauthenticated_page_redirects_to_login(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert r.headers["location"] == "/login"


def test_login_wrong_password_redirects_with_error(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.post("/api/login", data={"user": "admin", "pass": "wrong"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login?e=1"


def test_login_correct_password_sets_cookie_and_grants_access(monkeypatch):
    client = _client_with_auth(monkeypatch)
    r = client.post("/api/login", data={"user": "admin", "pass": "secret123"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert "dash_auth" in r.cookies
    r2 = client.get("/api/reference")
    assert r2.status_code == 200


def test_find_analyze_downloads_extracts_analyzes_and_saves(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    # 실제 운영 DB(shopping_shorts/data/reference.db)를 절대 건드리지 않도록
    # app_module에 바인딩된 DB_PATH를 tmp_path 격리 DB로 교체한다.
    # (config.DB_PATH만 monkeypatch하면 app.py가 모듈 로드 시 이미 바인딩해둔
    #  이름은 그대로라서 실DB에 계속 쓰게 된다 — app_module.DB_PATH를 직접 바꿔야 함)
    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)

    # 마지막 수집 결과에 분석 대상 아이템을 하나 심어둔다
    store = Store(test_db_path)
    store.save_last_run([{
        "shortcode": "sc1", "video_url": "https://example.com/v.mp4",
        "caption": "여름 바닥 청소", "thumbnail": "t.jpg",
    }], "2026-07-09T00:00:00Z")

    monkeypatch.setattr(app_module, "download_video", lambda url, dest: tmp_path / "v.mp4")
    (tmp_path / "v.mp4").write_bytes(b"fake")
    monkeypatch.setattr(app_module, "extract_frames",
                         lambda video_path, dest, max_frames: [tmp_path / "frame_01.jpg"])
    (tmp_path / "frame_01.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(app_module, "analyze_video", lambda path, caption: {
        "keywords": {"ko": ["바닥 청소"], "en": ["floor cleaner"], "zh": ["地板清洁"]},
        "category": "생활용품/홈케어",
    })

    r = client.post("/api/find/analyze", params={"shortcode": "sc1"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["keywords"]["ko"] == ["바닥 청소"]
    assert "youtube" in d["search_links"]
    assert len(d["frame_urls"]) == 1

    # 저장도 됐는지
    saved = store.get_source_analysis("sc1")
    assert saved["keywords"]["ko"] == ["바닥 청소"]


def test_find_analyze_prepends_identified_product_name_to_ko_en_only(monkeypatch, client, tmp_path):
    """구글 렌즈로 확인한 정확한 제품명을 ko/en 키워드 맨 앞에만 추가한다.
    zh/ja/ru까지 똑같은 문자열을 넣으면 언어 드롭다운을 바꿔도 검색어 자체가
    안 바뀌어 매번 같은 영상만 나오는 버그가 있었음(2026-07-10 실측 피드백
    "언어 바꿔도 다 똑같은 영상 나온다") — zh/ja/ru는 Gemini가 이미 만든 그
    언어 고유 키워드를 그대로 둬야 언어별로 실제 다른 검색이 된다."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_last_run([{
        "shortcode": "sc1", "video_url": "https://example.com/v.mp4",
        "caption": "전자노트 리뷰", "thumbnail": "t.jpg",
    }], "2026-07-09T00:00:00Z")

    monkeypatch.setattr(app_module, "download_video", lambda url, dest: tmp_path / "v.mp4")
    (tmp_path / "v.mp4").write_bytes(b"fake")
    monkeypatch.setattr(app_module, "extract_frames",
                         lambda video_path, dest, max_frames: [tmp_path / "frame_01.jpg"])
    (tmp_path / "frame_01.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(app_module, "analyze_video", lambda path, caption: {
        "keywords": {"ko": ["전자노트"], "en": ["digital notebook"], "zh": ["电子笔记本"],
                     "ja": ["電子ノート"], "ru": ["электронный блокнот"]},
        "category": "가전/디지털",
    })
    monkeypatch.setattr(app_module, "identify_product", lambda frame_urls, category, caption: "reMarkable Paper Pro")

    r = client.post("/api/find/analyze", params={"shortcode": "sc1"})
    assert r.status_code == 200
    d = r.json()
    assert d["keywords"]["ko"] == ["reMarkable Paper Pro", "전자노트"]
    assert d["keywords"]["en"] == ["reMarkable Paper Pro", "digital notebook"]
    # zh/ja/ru는 손대지 않음 — Gemini가 만든 그 언어 고유 키워드 그대로
    assert d["keywords"]["zh"] == ["电子笔记本"]
    assert d["keywords"]["ja"] == ["電子ノート"]
    assert d["keywords"]["ru"] == ["электронный блокнот"]

    saved = store.get_source_analysis("sc1")
    assert saved["keywords"]["ko"] == ["reMarkable Paper Pro", "전자노트"]


def test_find_analyze_identify_product_failure_does_not_break_analyze(monkeypatch, client, tmp_path):
    """SerpApi/Gemini 오류로 제품명 확인이 실패해도 분석 자체는 계속 진행한다."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_last_run([{
        "shortcode": "sc1", "video_url": "https://example.com/v.mp4",
        "caption": "", "thumbnail": "t.jpg",
    }], "2026-07-09T00:00:00Z")

    monkeypatch.setattr(app_module, "download_video", lambda url, dest: tmp_path / "v.mp4")
    (tmp_path / "v.mp4").write_bytes(b"fake")
    monkeypatch.setattr(app_module, "extract_frames",
                         lambda video_path, dest, max_frames: [tmp_path / "frame_01.jpg"])
    (tmp_path / "frame_01.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(app_module, "analyze_video", lambda path, caption: {
        "keywords": {"ko": ["전자노트"], "en": [], "zh": [], "ja": [], "ru": []},
        "category": "가전/디지털",
    })
    def fake_identify_product(frame_urls, category, caption):
        raise RuntimeError("SerpApi 429")
    monkeypatch.setattr(app_module, "identify_product", fake_identify_product)

    r = client.post("/api/find/analyze", params={"shortcode": "sc1"})
    assert r.status_code == 200
    d = r.json()
    assert d["keywords"]["ko"] == ["전자노트"]


def test_find_analyze_unknown_shortcode_404(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module

    # 이 엔드포인트도 store.load_last_run()으로 실DB를 읽으므로 동일하게 격리한다.
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "test.db")
    # last_run에 없으면 Apify 단일조회로 폴백한다(2026-07-09) — 그것도 없으면(비공개/
    # 삭제) 404. 실 네트워크 호출 방지를 위해 모킹.
    monkeypatch.setattr(app_module, "fetch_single_reel", lambda url: None)

    r = client.post("/api/find/analyze", params={"shortcode": "https://www.instagram.com/reel/nope/"})
    assert r.status_code == 404


def test_find_analyze_untracked_url_falls_back_to_apify_single_fetch(monkeypatch, client, tmp_path):
    """추적 채널 목록(last_run)에 없는 URL이어도 Apify 단일조회로 즉시 가져와
    분석한다(2026-07-09, "우리 목록에 없으면 분석 불가" 제약 제거)."""
    from shopping_shorts import app as app_module

    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "test.db")

    def fake_fetch_single_reel(url):
        assert url == "https://www.instagram.com/reel/newone/"
        return {"url": "https://www.instagram.com/p/newone/",
                "videoUrl": "https://example.com/new.mp4", "caption": "새 영상"}
    monkeypatch.setattr(app_module, "fetch_single_reel", fake_fetch_single_reel)

    monkeypatch.setattr(app_module, "download_video", lambda url, dest: tmp_path / "v.mp4")
    (tmp_path / "v.mp4").write_bytes(b"fake")
    monkeypatch.setattr(app_module, "extract_frames",
                         lambda video_path, dest, max_frames: [tmp_path / "frame_01.jpg"])
    (tmp_path / "frame_01.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(app_module, "analyze_video", lambda path, caption: {
        "keywords": {"ko": ["새 제품"], "en": ["new product"], "zh": ["新产品"]},
        "category": "기타",
    })

    r = client.post("/api/find/analyze", params={"shortcode": "https://www.instagram.com/reel/newone/"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["shortcode"] == "https://www.instagram.com/p/newone/"
    assert d["keywords"]["ko"] == ["새 제품"]


def test_find_analyze_apify_single_fetch_failure_returns_clean_error(monkeypatch, client, tmp_path):
    """Apify 단일조회 자체가 실패(네트워크·계정소진 등)하면 raw 500 대신 502."""
    from shopping_shorts import app as app_module

    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "test.db")

    def fake_fetch_single_reel(url):
        raise RuntimeError("apify 토큰 4개 전부 실패")
    monkeypatch.setattr(app_module, "fetch_single_reel", fake_fetch_single_reel)

    r = client.post("/api/find/analyze", params={"shortcode": "https://www.instagram.com/reel/x/"})
    assert r.status_code == 502
    assert r.json()["ok"] is False


def test_find_analyze_non_instagram_url_returns_clean_error_without_calling_apify(monkeypatch, client, tmp_path):
    """유튜브 등 인스타그램이 아닌 URL은 Apify 호출 자체를 스킵하고 즉시 명확한
    에러를 반환한다(2026-07-09) — 이 액터는 인스타 전용이라, 스킵 안 하면 계정
    7개를 전부 돌면서 매번 "input.username is required"로 실패하고 "토큰 전부
    소진"처럼 오해를 낳는 사고가 있었음."""
    from shopping_shorts import app as app_module

    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "test.db")

    def fail(*a, **kw):
        raise AssertionError("인스타그램 URL이 아니면 fetch_single_reel을 호출하면 안 된다")
    monkeypatch.setattr(app_module, "fetch_single_reel", fail)

    r = client.post("/api/find/analyze", params={"shortcode": "https://youtu.be/ktIkVeTp76w"})
    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_find_analyze_matches_raw_instagram_url_with_tracking_params(monkeypatch, client, tmp_path):
    """사용자가 인스타그램 앱에서 그대로 복사한 URL(추적파라미터 포함, /reel/ 형식)을
    붙여넣어도 저장된 shortcode(/p/ 형식, 파라미터 없음)와 같은 항목으로 매칭돼야
    한다(2026-07-09, "해당 항목 없음" 오탐 수정) — 응답의 shortcode는 canonical
    값으로 정규화되어야 한다."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_last_run([{
        "shortcode": "https://www.instagram.com/p/DajcIMgh3iv/",
        "video_url": "https://example.com/v.mp4",
        "caption": "실링팬", "thumbnail": "t.jpg",
    }], "2026-07-09T00:00:00Z")

    monkeypatch.setattr(app_module, "download_video", lambda url, dest: tmp_path / "v.mp4")
    (tmp_path / "v.mp4").write_bytes(b"fake")
    monkeypatch.setattr(app_module, "extract_frames",
                         lambda video_path, dest, max_frames: [tmp_path / "frame_01.jpg"])
    (tmp_path / "frame_01.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(app_module, "analyze_video", lambda path, caption: {
        "keywords": {"ko": ["실링팬"], "en": ["ceiling fan"], "zh": ["吊扇"]},
        "category": "생활가전",
    })

    raw_url = "https://www.instagram.com/reel/DajcIMgh3iv/?utm_source=ig_web_copy_link&igsh=abc"
    r = client.post("/api/find/analyze", params={"shortcode": raw_url})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["shortcode"] == "https://www.instagram.com/p/DajcIMgh3iv/"

    saved = store.get_source_analysis("https://www.instagram.com/p/DajcIMgh3iv/")
    assert saved["keywords"]["ko"] == ["실링팬"]


def test_find_analyze_download_failure_returns_clean_error(monkeypatch, client, tmp_path):
    """인스타 서명URL 만료 등으로 download_video가 requests.HTTPError를 던지면
    500 스택트레이스 대신 명확한 JSON 에러(2026-07-09, 최종 리뷰 Finding 1 —
    download→extract→analyze 구간이 무가드였던 문제)."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_last_run([{
        "shortcode": "sc1", "video_url": "https://example.com/expired.mp4",
        "caption": "여름 바닥 청소", "thumbnail": "t.jpg",
    }], "2026-07-09T00:00:00Z")

    def fake_download_video(url, dest):
        raise requests.HTTPError("404 Client Error: Not Found for url")

    monkeypatch.setattr(app_module, "download_video", fake_download_video)

    r = client.post("/api/find/analyze", params={"shortcode": "sc1"})
    assert r.status_code == 502
    d = r.json()
    assert d["ok"] is False
    assert "error" in d


def test_find_analyze_missing_video_url_returns_clean_error(monkeypatch, client, tmp_path):
    """last_run 항목에 video_url 필드 자체가 없으면(기능 추가 이전에 수집된 레코드
    등) item["video_url"]의 KeyError 대신 명확한 400계열 에러(2026-07-09, 최종
    리뷰 Finding 1)."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_last_run([{
        "shortcode": "sc1", "caption": "여름 바닥 청소", "thumbnail": "t.jpg",
        # video_url 없음
    }], "2026-07-09T00:00:00Z")

    def fail(*a, **kw):
        raise AssertionError("video_url 없이 download_video를 호출하면 안 된다")

    monkeypatch.setattr(app_module, "download_video", fail)

    r = client.post("/api/find/analyze", params={"shortcode": "sc1"})
    assert r.status_code in (400, 422)
    d = r.json()
    assert d["ok"] is False


def test_find_frame_rejects_path_traversal(client):
    """work_id="..", filename=<실제파일명> 이면 슬래시 하나 없이도
    _FIND_TMP_DIR(data/find_frames/)의 부모 디렉터리(data/)로 탈출해서
    실DB(reference.db) 같은 임의 파일을 서빙할 수 있었던 취약점 회귀 테스트.

    ".."을 URL에 그대로 쓰면 httpx가 요청 전송 전에 클라이언트 사이드에서
    dot-segment를 정규화해버려(RFC 3986) "/api/find/frame/../reference.db"가
    "/api/find/reference.db"로 바뀌고, 이는 라우트 자체가 안 맞아 애초에
    404가 나므로 수정 여부와 무관하게 항상 통과하는 가짜 테스트가 된다.
    그래서 %2e%2e로 퍼센트인코딩해 클라이언트 정규화를 우회하고, 서버(Starlette)가
    이를 그대로 문자열 ".."인 path param으로 넘기게 만든다 — 실제 공격 벡터와 동일.
    수정 전 코드였다면 이 요청은 200 + reference.db 바이트를 반환했다(수동 확인됨)."""
    from shopping_shorts import app as app_module

    # _FIND_TMP_DIR 밖(부모 디렉터리인 data/)에 실제로 존재하는 파일을 대상으로
    # "work_id=..", filename=그 파일명" 으로 탈출을 시도한다.
    assert app_module.DB_PATH.parent == app_module._FIND_TMP_DIR.parent
    target_name = app_module.DB_PATH.name  # "reference.db" — data/ 바로 아래 실재하는 파일

    r = client.get(f"/api/find/frame/%2e%2e/{target_name}")
    assert r.status_code == 404
    assert r.content != app_module.DB_PATH.read_bytes()


def test_find_preview_returns_six_items_tagged_with_lang(monkeypatch, client, tmp_path):
    """플랫폼 1개+언어 1개로 채점 없이 빠르게 미리보기(2026-07-10, 실수집+Gemini
    채점 섹션이 느리고 부정확해서("여기 나온건 의미가 없다") 제거하고 대체)."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_source_analysis("sc1", keywords={"ko": ["바닥 청소"], "en": ["floor cleaner"], "zh": [], "ja": [], "ru": []},
                                frame_paths=["/tmp/f1.jpg"], analyzed_at="2026-07-09T00:00:00Z")

    captured = {}
    def fake_youtube_search(kw, max_results):
        captured["kw"] = kw
        captured["max_results"] = max_results
        return [{"url": "https://youtube.com/watch?v=x", "title": "t", "thumbnail": "th.jpg"}]
    monkeypatch.setattr(app_module, "youtube_search_fn", fake_youtube_search)

    r = client.get("/api/find/preview", params={"shortcode": "sc1", "platform": "youtube", "lang": "ko"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert captured["kw"] == "바닥 청소"
    assert captured["max_results"] == 6
    assert d["items"][0]["url"] == "https://youtube.com/watch?v=x"
    assert d["items"][0]["source_lang"] == "ko"
    assert isinstance(d["items"][0]["id"], int)

    # 저장도 됐는지(+담기 버튼이 이 id를 참조)
    r2 = client.get("/api/find/candidates", params={"shortcode": "sc1"})
    assert r2.json()["items"][0]["source_lang"] == "ko"


def test_find_preview_no_analysis_404(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "test.db")

    r = client.get("/api/find/preview", params={"shortcode": "never-analyzed", "platform": "youtube"})
    assert r.status_code == 404


def test_find_preview_unsupported_platform_400(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_source_analysis("sc1", keywords={"ko": [], "en": ["floor cleaner"], "zh": [], "ja": [], "ru": []},
                                frame_paths=["/tmp/f1.jpg"], analyzed_at="2026-07-09T00:00:00Z")

    r = client.get("/api/find/preview", params={"shortcode": "sc1", "platform": "facebook"})
    assert r.status_code == 400


def test_find_preview_unsupported_lang_400(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_source_analysis("sc1", keywords={"ko": ["k"], "en": [], "zh": [], "ja": [], "ru": []},
                                frame_paths=["/tmp/f1.jpg"], analyzed_at="2026-07-09T00:00:00Z")

    r = client.get("/api/find/preview", params={"shortcode": "sc1", "platform": "youtube", "lang": "fr"})
    assert r.status_code == 400


def test_find_preview_missing_keyword_for_lang_returns_empty(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_source_analysis("sc1", keywords={"ko": ["k"], "en": [], "zh": [], "ja": [], "ru": []},
                                frame_paths=["/tmp/f1.jpg"], analyzed_at="2026-07-09T00:00:00Z")

    r = client.get("/api/find/preview", params={"shortcode": "sc1", "platform": "youtube", "lang": "ja"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "items": []}


def test_find_preview_no_youtube_key_returns_clean_error(monkeypatch, client, tmp_path):
    """YOUTUBE_API_KEY 미설정 시 500 대신 명확한 에러(2026-07-09, 배포 후 실단말 검증 중
    raw 500 확인하고 수정 — youtube_search.search()의 RuntimeError가 잡히지 않았음)."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_source_analysis("sc1", keywords={"ko": [], "en": ["floor cleaner"], "zh": [], "ja": [], "ru": []},
                                frame_paths=["/tmp/f1.jpg"], analyzed_at="2026-07-09T00:00:00Z")

    def fake_search(kw, max_results):
        raise RuntimeError("youtube_search: YOUTUBE_API_KEY가 설정되지 않았습니다")
    monkeypatch.setattr(app_module, "youtube_search_fn", fake_search)

    r = client.get("/api/find/preview", params={"shortcode": "sc1", "platform": "youtube", "lang": "en"})
    assert r.status_code == 503
    assert r.json()["ok"] is False


def test_find_preview_youtube_quota_error_returns_clean_503(monkeypatch, client, tmp_path):
    """YouTube Data API 쿼터 소진(403)·레이트리밋 등은 RuntimeError가 아니라
    requests.HTTPError(=requests.RequestException)로 온다 — RuntimeError만
    잡던 예전 except절은 이 경로를 놓쳐서 raw 500이 났다(2026-07-09, 최종
    리뷰 Finding 2)."""
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    store.save_source_analysis("sc1", keywords={"ko": [], "en": ["floor cleaner"], "zh": [], "ja": [], "ru": []},
                                frame_paths=["/tmp/f1.jpg"], analyzed_at="2026-07-09T00:00:00Z")

    def fake_search(kw, max_results):
        raise requests.HTTPError("403 Client Error: quotaExceeded")
    monkeypatch.setattr(app_module, "youtube_search_fn", fake_search)

    r = client.get("/api/find/preview", params={"shortcode": "sc1", "platform": "youtube", "lang": "en"})
    assert r.status_code == 503
    assert r.json()["ok"] is False


def test_find_save_adds_candidate_to_pool(monkeypatch, client, tmp_path):
    from shopping_shorts import app as app_module
    from shopping_shorts.store import Store

    test_db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db_path)
    store = Store(test_db_path)
    ids = store.save_candidates("sc1", "youtube", [
        {"url": "https://youtube.com/watch?v=x", "title": "t", "thumbnail": "th.jpg"},
    ])

    r = client.post("/api/find/save", params={"candidate_id": ids[0], "shortcode": "sc1"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    pool = store.pool_items()
    assert len(pool) == 1
    assert pool[0]["origin_shortcode"] == "sc1"
