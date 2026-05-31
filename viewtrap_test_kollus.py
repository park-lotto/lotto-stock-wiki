# -*- coding: utf-8 -*-
import sys, io, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

LECTURE_URL = "https://viewtrap.com/business/lectures?curriculumId=69c49d3474de71e13f64ea7b&videoKey=VzXe3cXF"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    # 네트워크에서 m3u8 캡처
    m3u8_urls = []
    def on_request(req):
        if "m3u8" in req.url or "kollus.com" in req.url:
            m3u8_urls.append(req.url)

    page = ctx.new_page()
    page.on("request", on_request)

    page.goto(LECTURE_URL, wait_until="networkidle")

    # 10초 대기하면서 KollusAgent 체크 통과 기다리기
    for i in range(10):
        time.sleep(2)
        for fr in page.frames:
            if "kollus" in fr.url:
                try:
                    txt = fr.inner_text("body")
                    v = fr.query_selector("video")
                    src = v.get_attribute("src") if v else ""
                    print(f"[{(i+1)*2}초] frame: {txt[:80]} | video src: {src[:80]}")

                    # m3u8 소스코드에서 탐색
                    html = fr.content()
                    found = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
                    if found:
                        print(f"  m3u8 발견: {found[0][:150]}")
                except: pass
        if m3u8_urls:
            print("\n네트워크 m3u8 요청 발견!")
            for u in m3u8_urls:
                print(f"  {u[:200]}")
            break

    print("\n=== 최종 네트워크 요청 (kollus) ===")
    for u in m3u8_urls:
        print(u[:200])

    page.close()
    browser.close()
