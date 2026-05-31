# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright
import time

URL = "https://contents.premium.naver.com/smstockstudy/1028/contents?categoryId=192ecb61fa3000awt"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    page.goto(URL)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # 글 목록 수집
    links = page.query_selector_all("a")
    posts = []
    seen = set()
    for link in links:
        href = link.get_attribute("href") or ""
        if "/contents/" in href and "categoryId" not in href:
            title_el = link.query_selector("strong, p")
            title = title_el.inner_text().strip() if title_el else link.inner_text().strip()
            date_el = link.query_selector("span, time")
            if title and href not in seen:
                seen.add(href)
                posts.append((title, href))

    print(f"=== 동주 카테고리 글 목록 ({len(posts)}개) ===")
    for i, (title, href) in enumerate(posts[:30], 1):
        print(f"{i}. {title}")
        print(f"   https://contents.premium.naver.com{href}")

    page.close()
    browser.close()
