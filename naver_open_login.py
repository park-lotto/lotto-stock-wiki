# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    # 네이버 로그인 페이지로 이동
    page.goto("https://nid.naver.com/nidlogin.login?url=https://contents.premium.naver.com/smstockstudy/1028/contents/260531215905700ap")
    print("Chrome 창에서 네이버 로그인 후 Enter 누르세요...")
    input()  # 사용자가 로그인할 때까지 대기
    # 로그인 후 프리미엄 페이지로 이동
    page.goto("https://contents.premium.naver.com/smstockstudy/1028/contents/260531215905700ap")
    page.wait_for_load_state("networkidle")
    body = page.inner_text("body")
    if "프리미엄 구독자 전용" in body:
        print("[FAIL] 아직 로그인 안됨")
    else:
        print("[OK] 접근 성공!\n")
        print(body[:5000])
    browser.close()
