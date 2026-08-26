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
import sys

from playwright.sync_api import sync_playwright

# ★BROWSER_HEADERS·THREADS_BASE·fetch_html은 threads_parse.py가 정본이다(순수 HTTP,
#   playwright 비의존). 여기서는 재수출만 한다 — 기존 호출부(threads_playwright.fetch_html
#   등)가 그대로 동작하게(2026-08-17, 담기 메타보강 1건마다 playwright를 끌어오던 문제 해소).
from shopping_shorts.threads_parse import (BROWSER_HEADERS, THREADS_BASE,
                                           extract_post_nodes, fetch_html,
                                           merge_thread_tail, parse_post_node,
                                           quality_score)


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


def _fetch_profile_nodes(username, session_path="", proxy=""):
    """프로필 HTML을 받아 게시물 노드를 모은다(순서 보존).

    session_path·proxy는 받아만 두고 이 경로에선 쓰지 않는다 — 로그아웃 뷰가 더 많이 준다.
    메타가 헤더 요구를 강화해 이 길이 막히면 그때 Playwright 경로로 폴백한다.

    ★조용한 실패 금지: "HTML을 아예 못 받았다"(네트워크·차단)와 "받았는데 노드가
      0개다"(파서가 구조 변화를 못 따라감)는 원인이 다르다 — 로그에서 갈라 보이게
      HTML 길이와 뽑은 노드 수를 함께 남긴다.
    """
    html = fetch_html(f"{THREADS_BASE}/@{username}")
    nodes = extract_post_nodes(html)
    if not nodes:
        reason = "HTML 수신 실패(0바이트)" if not html else "파서가 노드를 못 찾음(구조 변화 의심)"
        print(f"[threads_playwright] _fetch_profile_nodes 0건 username={username} "
              f"html_len={len(html)} nodes=0 ({reason})", file=sys.stderr)
    return nodes


def collect_account(username, store, session_path="", proxy=""):
    """계정 하나를 수집해 저장한다. {"posts": 저장대상 수, "new": 새로 들어온 수}."""
    nodes = _fetch_profile_nodes(username, session_path, proxy)
    parsed = [p for p in (parse_post_node(n, username) for n in nodes) if p]
    merged = merge_thread_tail(parsed)
    new = 0
    for post in merged:
        post["quality"] = quality_score(post)
        post["source"] = "account"
        if store.threads_upsert(post):
            new += 1
    return {"posts": len(merged), "new": new}


def fetch_video_url(code, username, session_path="", proxy=""):
    """/post/{code}/media 로 들어가 mp4 직링크를 회수한다. 실패하면 빈 문자열.

    ★이 경로가 있는 이유(2026-08-17 실측): 프로필 목록엔 <video>가 아예 없고
      커버 이미지만 있다. 이 URL로 들어가야 <video>가 뜬다. 그리고 쓰레드 영상은
      blob/MSE가 아니라 통짜 mp4(content-type video/mp4, ftypisom, Range 206)라
      주소만 얻으면 그대로 받을 수 있다.
    ★이 주소는 만료된다. 영구 주소로 믿지 말고, 필요할 때 다시 부른다.
    """
    from playwright.sync_api import TimeoutError as PWTimeoutError
    src = ""
    logged = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(**_context_kw(session_path, proxy))
        page = ctx.new_page()
        try:
            page.goto(f"{THREADS_BASE}/@{username}/post/{code}/media",
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("video", timeout=20000)
            src = page.eval_on_selector("video", "v => v.currentSrc || v.src || ''")
        except PWTimeoutError as e:
            print(f"[threads_playwright] fetch_video_url 타임아웃 code={code} "
                  f"username={username} {e!r}", file=sys.stderr)
            src, logged = "", True
        except Exception as e:
            print(f"[threads_playwright] fetch_video_url 실패 code={code} "
                  f"username={username} {e!r}", file=sys.stderr)
            src, logged = "", True
        finally:
            browser.close()
    if not (isinstance(src, str) and src.startswith("https://")):
        if not logged:
            print(f"[threads_playwright] fetch_video_url video 태그 없음/빈 src "
                  f"code={code} username={username}", file=sys.stderr)
        return ""
    return src
