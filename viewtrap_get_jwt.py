# -*- coding: utf-8 -*-
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

LECTURE_URL = "https://viewtrap.com/business/lectures?curriculumId=69c49d3474de71e13f64ea7b&videoKey=VzXe3cXF"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    page.goto(LECTURE_URL, wait_until="networkidle")
    time.sleep(3)

    # Kollus iframe 전체 URL 출력
    iframe = page.query_selector("iframe#kollus-player")
    if iframe:
        src = iframe.get_attribute("src")
        print("KOLLUS_URL:" + src)

    # API로 토큰 직접 요청
    token_data = page.evaluate("""async () => {
        const r = await fetch('https://api.viewtrap.com/api/v2/vod/revise/token?videoKey=VzXe3cXF&curriculumId=69c49d3474de71e13f64ea7b&mobileYn=N', {credentials:'include'});
        return await r.json();
    }""")
    if token_data.get('data', {}).get('token'):
        print("JWT:" + token_data['data']['token'])
        print("CUSTOM_KEY:" + token_data['data'].get('custom_key',''))

    page.close()
    browser.close()
