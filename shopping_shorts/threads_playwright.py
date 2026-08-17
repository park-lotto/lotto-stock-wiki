"""쓰레드 수집 — Playwright로 실제 게시물 데이터가 담긴 응답을 가로챈다.

★인페이지 JS 후킹(window.fetch 덮어쓰기)은 쓰지 마라. 메타 코드가 부팅 시점에
  원본 fetch/XHR을 선점해 우리 후킹이 안 걸린다(2026-08-17 실측: 캡처 0건).
  반드시 Playwright 레벨(page.on("response"))에서 가로챈다.

★URL에 "graphql"이 들어간 응답만 거르면 0건이 된다(2026-08-17 서버 실측).
  인스타그램 세션 쿠키는 .instagram.com 도메인에만 있어 threads.com에는
  안 먹는다 → 프로필 라우트가 "로그아웃 상태"(barcelonawebloggedout)로
  렌더링되고, 이 모드에서는 게시물 데이터가 별도 GraphQL XHR이 아니라
  **최초 문서 응답(SSR HTML) 안에 인라인 JSON으로** 들어 있다
  (실측: /ajax/bz, /ajax/bulk-route-definitions/ 응답엔 caption 등이
  전혀 없고, 최초 page.goto 문서 응답 본문에는 caption·like_count·
  video_versions가 전부 True). 그래서 URL 패턴이 아니라 **본문 안에 실제
  게시물 마커(caption/like_count/video_versions)가 있는지**로 거른다.
"""
import json

from playwright.sync_api import sync_playwright

THREADS_BASE = "https://www.threads.com"


def _context_kw(session_path="", proxy=""):
    """세션·프록시를 한 곳에서 짝으로 정한다.

    ★조건부로 정한 값을 아래에서 무조건 덮어쓰지 마라(0순위-B). 계정과 IP가
      어긋난 채 나가면 인스타·쓰레드가 본인확인 챌린지를 띄운다.
    """
    from shopping_shorts.channel_archive import playwright_proxy_kw
    kw = {"locale": "ko-KR"}
    if session_path:
        kw["storage_state"] = session_path
        if proxy:
            pk = playwright_proxy_kw(proxy)
            if pk:
                kw["proxy"] = pk
    return kw


def dump_profile_payloads(username, out_path, session_path="", proxy=""):
    """프로필을 열고 오간 GraphQL 응답을 전부 파일에 남긴다(설계용 1회성 도구)."""
    seen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(**_context_kw(session_path, proxy))
        page = ctx.new_page()

        def on_response(res):
            if "threads.com" not in res.url:
                return
            try:
                body = res.text()
            except Exception:
                return        # 본문을 못 읽는 응답은 조용히 건너뛴다
            if not any(m in body for m in ("caption", "like_count", "video_versions")):
                return        # 실제 게시물 데이터가 없는 응답은 저장하지 않는다
            seen.append({"url": res.url, "body": body})

        page.on("response", on_response)
        page.goto(f"{THREADS_BASE}/@{username}", wait_until="domcontentloaded",
                  timeout=60000)
        page.wait_for_timeout(6000)
        browser.close()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False)
    return len(seen)
