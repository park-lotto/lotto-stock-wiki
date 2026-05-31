# -*- coding: utf-8 -*-
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    page.goto("https://viewtrap.com/auth/login", wait_until="networkidle")
    time.sleep(2)

    # Google 로그인 버튼 클릭
    google_btn = page.query_selector("text=Google 계정으로 로그인")
    if google_btn:
        google_btn.click()
        print("Google 로그인 버튼 클릭됨 - Chrome 창에서 로그인 완료해주세요")
    else:
        print("버튼 못 찾음, 수동으로 클릭해주세요")
        print("현재 URL:", page.url)

    # 로그인 대기
    print("로그인 완료 후 Enter...")
    input()

    print("현재 URL:", page.url)
    print("제목:", page.title())
    page.close()
    browser.close()
