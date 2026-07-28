"""인스타 릴스 수집 — Playwright + 주거용 프록시(2026-07-28).

apify_client.fetch_reels와 **같은 계약**(10키 dict 리스트)을 돌려준다. 그래서
service.py는 어느 쪽을 쓰든 하류가 무변경이다.

설계 요점:
- DOM을 파싱하지 않는다. page.on("response")로 인스타가 스스로 부르는 JSON을 가로챈다.
  DOM에는 조회수·댓글수가 축약("1.2만")으로만 나오고, 인스타가 마크업을 수시로 바꾼다.
- 채널 하나가 실패해도 전체가 죽지 않는다(Apify 403이 통째로 죽이던 문제).
- 채널마다 on_progress를 부른다 — 50분간 아무 표시가 없어 사장님이 취소한 게 발단이다.

테스트는 _scrape_one을 주입해 브라우저 없이 돈다(test_instagram_playwright.py).
"""
import os

from shopping_shorts import config
from shopping_shorts.instagram_parse import (
    classify_channel_result, extract_reel_nodes, parse_reel_node,
)

# 마지막 실행의 분류 집계 — 호출부(service/app)가 job 결과에 담아 화면·보고에 쓴다.
# ★이 숫자가 부계정(B안) 도입 여부의 판단 근거다.
LAST_TALLY = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}

# 인스타가 릴스 목록을 채울 때 부르는 내부 API 경로 조각. 이 중 하나가 들어간
# 응답만 JSON으로 읽는다(이미지·폰트 등 나머지는 무시).
_REEL_API_HINTS = ("/api/v1/clips/user/", "/api/v1/feed/reels_media", "/graphql")


def _scrape_one_playwright(username):
    """채널 1개 → (nodes, page_url, error). 브라우저를 실제로 띄우는 유일한 함수.

    반환 계약을 (nodes, page_url, error) 세 값으로 고정한 이유: 분류(classify_channel_result)가
    이 세 가지만 있으면 판정할 수 있어, 테스트에서 통째로 대체하기 쉽다.
    """
    from playwright.sync_api import sync_playwright   # 지연 import — 미설치 환경에서 모듈 로드가 죽지 않게
    from playwright_stealth import Stealth   # navigator.webdriver 등 자동화 흔적 위장(2026-07-29 실사고)

    url = f"https://www.instagram.com/{username}/reels/"
    captured = []
    # AutomationControlled 끄기 — 로그인 세션(storage_state)이 CDP 흔적만으로 캡차 벽에
    # 걸리는 걸 막는다(2026-07-29 실사고, scripts/instagram_setup_session.py와 동일 조치).
    launch_kw = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
    ctx_kw = {}
    # 세션(storage_state)이 있으면 그걸로 로그인 상태 직결한다 — 샤오홍슈에서 검증된 대로
    # 프록시 없이도 되므로 프록시보다 우선한다. 없으면 기존 경로(프록시/직결)로 폴백.
    if config.INSTAGRAM_SESSION_PATH and os.path.exists(config.INSTAGRAM_SESSION_PATH):
        ctx_kw["storage_state"] = config.INSTAGRAM_SESSION_PATH
    elif config.INSTAGRAM_PROXY:
        ctx_kw["proxy"] = {"server": config.INSTAGRAM_PROXY}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kw)
            ctx = browser.new_context(**ctx_kw)
            Stealth().apply_stealth_sync(ctx)
            page = ctx.new_page()

            def _on_response(resp):
                if not any(h in resp.url for h in _REEL_API_HINTS):
                    return
                try:
                    captured.extend(extract_reel_nodes(resp.json()))
                except Exception:      # noqa: BLE001 — JSON이 아니거나 모양이 다르면 그냥 무시
                    pass

            page.on("response", _on_response)
            page.goto(url, timeout=config.INSTAGRAM_PW_TIMEOUT_MS,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(2500)          # 릴스 목록 XHR이 도착할 여유
            final_url = page.url
            ctx.close()
            browser.close()
        return captured, final_url, None
    except Exception as e:                        # noqa: BLE001 — 채널 하나의 실패로 전체가 죽지 않게
        return [], url, str(e)[:200]


def fetch_reels(usernames, on_progress=None, _scrape_one=None):
    """usernames → 10키 reel dict 리스트. apify_client.fetch_reels와 동일 계약.

    on_progress(done, total, items_so_far, tally): 채널 1개 끝날 때마다 호출(선택).
    _scrape_one: 테스트 주입용. 기본은 실제 Playwright 스크레이퍼.
    """
    scrape = _scrape_one or _scrape_one_playwright
    names = [(u or "").strip().lstrip("@") for u in (usernames or [])]
    names = [u for u in names if u]
    total = len(names)
    tally = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}
    items = []
    for i, uname in enumerate(names, start=1):
        nodes, page_url, error = scrape(uname)
        verdict = classify_channel_result(nodes, page_url, error)
        tally[verdict] = tally.get(verdict, 0) + 1
        if verdict == "ok":
            for n in nodes[:config.RESULTS_PER_CHANNEL]:
                d = parse_reel_node(n, uname)
                if d:
                    items.append(d)
        if on_progress:
            on_progress(i, total, len(items), dict(tally))
    LAST_TALLY.clear()
    LAST_TALLY.update(tally)
    return items
