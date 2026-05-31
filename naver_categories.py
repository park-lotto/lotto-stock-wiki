# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright
import time

BASE = "https://contents.premium.naver.com/smstockstudy/1028"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # 채널 메인 페이지로 이동
    page.goto(BASE + "/contents")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # 카테고리 목록 링크 수집
    links = page.query_selector_all("a")
    categories = []
    for link in links:
        href = link.get_attribute("href") or ""
        text = link.inner_text().strip()
        if "categoryId" in href and text:
            categories.append(f"{text} => {href}")

    print("=== 카테고리 목록 ===")
    for c in set(categories):
        print(c)

    page.close()
    browser.close()
