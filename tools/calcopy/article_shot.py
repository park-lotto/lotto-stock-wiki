# -*- coding: utf-8 -*-
"""기사 화면 캡처(단순 작업) — 기사 주소를 열어 제목·첫 문단이 보이는 윗부분을 세로 장면용으로 찍는다.
    PYTHONUTF8=1 py tools/calcopy/article_shot.py <url> <out.jpg>
모바일 크기(412x915, 배율 2.6)로 열어 광고·팝업을 지우고 위에서부터 찍는다. 장면에는 사진처럼(천천히 확대) 들어간다.
"""
import sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 412, "height": 915}, device_scale_factor=2.6, is_mobile=True,
                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148")
    pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(2500)
    pg.evaluate("""() => { for (const s of ['iframe','[class*=ad]','[id*=ad]','[class*=popup]','[class*=banner]','header .gnb']) {
        document.querySelectorAll(s).forEach(e => { if (e.offsetHeight < 600) e.remove(); }); } }""")
    h1 = pg.query_selector("h1, h2.title, .article_title, .headline")
    if h1:
        h1.scroll_into_view_if_needed(); pg.evaluate("window.scrollBy(0,-80)")
    pg.screenshot(path=out, type="jpeg", quality=85)
    b.close()
print(out)
