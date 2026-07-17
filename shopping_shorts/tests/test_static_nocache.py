"""정적 JS/CSS/HTML에도 no-cache — 배포해도 화면엔 안 뜨던 것(C-1, 2026-07-16 라이브 실증).

★실측: 서버는 새 sidebar.js(mountWorks 포함, 5957바이트)를 주고 있는데 화면의 .ss-work가
0개였다. performance.getEntriesByType('resource')의 sidebar 엔트리가
`transferSize: 0, cached: true` — 페이지가 옛 sidebar.js를 브라우저 캐시에서 실행 중이었다.
`/sidebar.js` 응답에 Cache-Control이 아예 없었다(etag는 있었음). Ctrl+Shift+R로는 바로 떴다.

원인: `app.mount("/", StaticFiles(...))`는 헤더를 안 붙인다. `_NOCACHE`는 그 위의 클린 URL
라우트(/produce 등)에만 붙어 있었다 — 정적 자산 자체(StaticFiles가 서빙하는 js/css/html)는
빠져 있었다. 이 저장소가 이미 한 번 만난 함정의 절반만 막혀 있었다(2026-07-14 HTML 캐시
사고 때 페이지 라우트만 고치고 정적 JS는 안 고침).

고친 방식: StaticFiles 서브클래스(_NoCacheStaticFiles)로 js/css/html 확장자에만
no-cache를 씌운다. 폰트(otf/ttf)는 내용이 안 바뀌는 자산이라 그대로 영구 캐시 — 여기 씌우면
사장님 화면이 매번 폰트를 다시 받는 역효과가 난다(과잉적용 금지, 반대편 봉인).
"""
from fastapi.testclient import TestClient

from shopping_shorts.app import app

client = TestClient(app)


def test_sidebar_js_has_nocache_header():
    """정적 JS는 배포 직후 브라우저가 바로 새 버전을 물어봐야 한다."""
    r = client.get("/sidebar.js")
    assert r.status_code == 200
    cc = (r.headers.get("cache-control") or "").lower()
    assert cc, "cache-control이 없다 — 브라우저가 옛 sidebar.js를 무기한 실행한다(2026-07-16 실사고)"
    assert "no-cache" in cc


def test_sidebar_js_still_serves_the_actual_bytes():
    """캐시 헤더 씌우느라 정적 서빙 자체가 깨지면 본말전도다."""
    r = client.get("/sidebar.js")
    assert r.status_code == 200
    assert "mountWorks" in r.text


def test_clean_url_routes_still_nocache():
    """/produce 등 기존 클린 URL 라우트(_NOCACHE)가 이번 변경으로 안 깨졌는가."""
    r = client.get("/produce")
    assert r.status_code == 200
    cc = (r.headers.get("cache-control") or "").lower()
    assert "no-cache" in cc


def test_html_served_via_static_mount_also_nocache():
    """확장자 없는 클린 URL이 아니라 옛 방식(.html 직접 접근)으로 와도 캐시 함정을 피한다."""
    r = client.get("/index.html")
    assert r.status_code == 200
    cc = (r.headers.get("cache-control") or "").lower()
    assert "no-cache" in cc


def test_fonts_are_not_force_revalidated():
    """폰트는 내용이 안 바뀐다 — no-cache를 씌우면 매번 서버 왕복만 늘어난다(과잉적용 금지)."""
    import os

    font_dir = os.path.join(os.path.dirname(__file__), "..", "static", "fonts")
    fname = sorted(os.listdir(font_dir))[0]
    r = client.get(f"/fonts/{fname}")
    assert r.status_code == 200
    assert "no-cache" not in (r.headers.get("cache-control") or "").lower()


def test_revalidation_304_still_carries_nocache_header():
    """etag로 304를 받아도 no-cache가 살아 있어야 다음 요청도 계속 재검증한다."""
    r1 = client.get("/sidebar.js")
    etag = r1.headers.get("etag")
    assert etag, "etag가 없으면 304 자체가 안 나온다"
    r2 = client.get("/sidebar.js", headers={"if-none-match": etag})
    assert r2.status_code == 304
    assert "no-cache" in (r2.headers.get("cache-control") or "").lower()


def test_missing_static_file_still_404s():
    """마운트 서브클래싱이 존재하지 않는 파일 처리(404)를 안 깨는지."""
    r = client.get("/does-not-exist.js")
    assert r.status_code == 404
