# -*- coding: utf-8 -*-
import sys, io, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

LECTURE_URL = "https://viewtrap.com/business/lectures?curriculumId=69c49d3474de71e13f64ea7b&videoKey=VzXe3cXF"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # 모든 네트워크 요청 캡처
    api_calls = []
    responses = {}
    def on_request(req):
        api_calls.append({"method": req.method, "url": req.url, "headers": dict(req.headers)})
    def on_response(resp):
        if "api.viewtrap.com" in resp.url or "vtt" in resp.url or "m3u8" in resp.url:
            try:
                body = resp.body()
                responses[resp.url] = body[:2000].decode('utf-8', errors='ignore')
            except: pass
    page.on("request", on_request)
    page.on("response", on_response)

    print("강의 페이지 진입...")
    page.goto(LECTURE_URL, wait_until="networkidle")
    time.sleep(4)

    print("URL:", page.url)
    print("제목:", page.title())

    # 페이지 텍스트
    print("\n=== 페이지 텍스트 ===")
    print(page.inner_text("body")[:3000])

    # 영상 플레이어 상세
    print("\n=== 영상 플레이어 ===")
    for sel in ["video", "iframe", "[class*='player']", "[class*='vod']", "[class*='video']"]:
        els = page.query_selector_all(sel)
        if els:
            print(f"[{sel}] {len(els)}개:")
            for el in els[:5]:
                attrs = {}
                for attr in ["src","data-src","data-url","data-video-id","id","class"]:
                    v = el.get_attribute(attr)
                    if v: attrs[attr] = v[:100]
                print(f"  {attrs}")

    # API 캡처
    print("\n=== API 요청 전체 (viewtrap 관련) ===")
    for c in api_calls:
        if "viewtrap" in c['url'] or "vtt" in c['url'] or "m3u8" in c['url']:
            print(f"  [{c['method']}] {c['url']}")

    # API 응답 내용
    print("\n=== API 응답 내용 ===")
    for url, body in responses.items():
        print(f"\n[{url[:80]}]")
        print(body[:500])

    # 소스코드에서 힌트
    print("\n=== 소스코드 키워드 ===")
    html = page.content()
    for kw in ["m3u8","vimeo","youtube","bunny","wistia","vtt","srt","subtitle","transcript","script_text","content_text","lecture_text"]:
        if kw.lower() in html.lower():
            idx = html.lower().index(kw.lower())
            print(f"  [{kw}] ...{html[max(0,idx-50):idx+100]}...")

    page.close()
    browser.close()
