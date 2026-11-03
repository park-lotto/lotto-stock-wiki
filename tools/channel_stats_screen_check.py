# 채널 리포트 화면 점검(관제 281): 로컬 앱(관리자)에서 영상 상세 서랍 열기/Esc 닫기·점 개수·오류. 사용: py tools/channel_stats_screen_check.py <캡처폴더>
import sys, time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8796/channel_stats", wait_until="networkidle"); time.sleep(2)
    pg.locator("#vTbl tr.click", has_text="딸기우유").first.scroll_into_view_if_needed()
    pg.screenshot(path=sys.argv[1] + "/tbl.png", clip={"x": 270, "y": 300, "width": 1170, "height": 420})
    pg.locator("#vTbl tr.click", has_text="딸기우유").first.click(); time.sleep(0.6)
    print("서랍 열림:", pg.evaluate("document.querySelector('#drawer').classList.contains('on')"), "점:", pg.locator("#drawer circle").count())
    pg.screenshot(path=sys.argv[1] + "/drawer.png", clip={"x": 790, "y": 0, "width": 650, "height": 900})
    pg.keyboard.press("Escape"); time.sleep(0.4)
    print("Esc 닫힘:", not pg.evaluate("document.querySelector('#drawer').classList.contains('on')"), "오류:", errs)
    b.close()
