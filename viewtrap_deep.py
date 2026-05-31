# -*- coding: utf-8 -*-
import sys, io, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # 네트워크 요청 캡처
    api_calls = []
    def on_request(req):
        if any(x in req.url for x in ["api","m3u8","mp4","vtt","srt","subtitle","caption","transcript"]):
            api_calls.append({"method": req.method, "url": req.url})
    page.on("request", on_request)

    # 강의 목록 페이지
    page.goto("https://viewtrap.com/training-room", wait_until="networkidle")
    time.sleep(2)

    # 강의 링크 수집
    links = page.query_selector_all("a")
    lecture_links = []
    for link in links:
        href = link.get_attribute("href") or ""
        text = link.inner_text().strip()
        if any(x in href for x in ["/lecture", "/lesson", "/video", "/content", "/course"]):
            lecture_links.append((text[:40], href))

    print(f"강의 링크 {len(lecture_links)}개 발견:")
    for t, h in lecture_links[:10]:
        print(f"  {t} -> {h}")

    # 강의 링크 없으면 버튼/카드 탐색
    if not lecture_links:
        print("\n직접 링크 없음 - 버튼 탐색:")
        btns = page.query_selector_all("button, [class*='lecture'], [class*='lesson'], [class*='content']")
        for b in btns[:10]:
            print(f"  [{b.tag_name}] {b.inner_text()[:40]}")

    # 첫 번째 강의 클릭 시도
    print("\n=== 강의 페이지 진입 시도 ===")
    first_lecture = page.query_selector("text=강의 보러 가기, text=이어서 학습하기, text=수강 전, [class*='lecture'], [href*='lecture']")
    if first_lecture:
        first_lecture.click()
        time.sleep(3)
        print("클릭 후 URL:", page.url)
    else:
        # URL 직접 시도
        page.goto("https://viewtrap.com/lecture", wait_until="networkidle")
        time.sleep(2)
        print("직접 이동 URL:", page.url)

    print("제목:", page.title())
    print("\n본문 텍스트:")
    print(page.inner_text("body")[:2000])

    # 영상 플레이어 탐색
    print("\n=== 영상 플레이어 분석 ===")
    for sel in ["video", "iframe", "[class*='player']", "[class*='vimeo']", "[class*='youtube']"]:
        els = page.query_selector_all(sel)
        if els:
            print(f"[{sel}] {len(els)}개:")
            for el in els[:3]:
                print(f"  src={el.get_attribute('src')} | data-src={el.get_attribute('data-src')}")

    # 자막 탐색
    print("\n=== 자막/스크립트 요소 ===")
    for sel in ["track", "[class*='caption']", "[class*='subtitle']", "[class*='transcript']", "[class*='script']"]:
        els = page.query_selector_all(sel)
        if els:
            print(f"[{sel}] {len(els)}개")
            for el in els[:2]:
                print(f"  {el.inner_text()[:100]}")

    # API 캡처 결과
    print("\n=== 캡처된 API 요청 ===")
    for call in api_calls[:20]:
        print(f"  [{call['method']}] {call['url']}")

    # 페이지 소스에서 힌트 찾기
    print("\n=== 소스코드 힌트 ===")
    html = page.content()
    for keyword in ["m3u8", "vimeo", "youtube", "wistia", "cloudflare", "bunny", "vtt", "subtitle", "transcript"]:
        if keyword.lower() in html.lower():
            idx = html.lower().index(keyword.lower())
            print(f"  [{keyword}] 발견: ...{html[max(0,idx-30):idx+80]}...")

    page.close()
    browser.close()
