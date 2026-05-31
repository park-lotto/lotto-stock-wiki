# -*- coding: utf-8 -*-
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    page.goto("https://viewtrap.com/training-room", wait_until="networkidle")
    time.sleep(3)

    print("현재 URL:", page.url)
    print("페이지 제목:", page.title())
    print("\n=== 페이지 텍스트 (앞 2000자) ===")
    print(page.inner_text("body")[:2000])

    # 영상 요소 탐색
    print("\n=== video 태그 ===")
    videos = page.query_selector_all("video")
    for v in videos:
        print(" src:", v.get_attribute("src"))
        sources = v.query_selector_all("source")
        for s in sources:
            print(" source:", s.get_attribute("src"))

    # iframe 탐색
    print("\n=== iframe ===")
    iframes = page.query_selector_all("iframe")
    for i in iframes:
        print(" src:", i.get_attribute("src"))

    # 자막/스크립트 탐색
    print("\n=== track (자막) ===")
    tracks = page.query_selector_all("track")
    for t in tracks:
        print(" kind:", t.get_attribute("kind"), "src:", t.get_attribute("src"))

    page.close()
    browser.close()
