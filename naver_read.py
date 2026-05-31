# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright
import time

URL = "https://contents.premium.naver.com/smstockstudy/1028/contents/260531215905700ap"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    body = page.inner_text("body")
    if "프리미엄 구독자 전용" in body:
        print("[FAIL] 아직 로그인 안됨")
        print(body[:300])
    else:
        print("[OK] 본문 접근 성공!\n")
        print(body[:6000])
    page.close()
    browser.close()
