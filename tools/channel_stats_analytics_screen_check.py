# 채널 리포트 애널리틱스 화면 점검(관제 281): 가짜 숫자 사본(CHSTATS_DIR)으로 띄운 로컬 앱(8797)에서 일별·연결·이탈 곡선 캡처. 사용: py tools/channel_stats_analytics_screen_check.py <캡처폴더>
import sys, time
from playwright.sync_api import sync_playwright
o = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8797/channel_stats?msg=테스트 알림", wait_until="networkidle"); time.sleep(2)
    pg.locator("#fCh button", has_text="꿀템샷").click(); time.sleep(1)
    pg.locator("#daily").scroll_into_view_if_needed(); time.sleep(.3)
    print("일별 보임:", pg.locator("#daily").is_visible(), "막대:", pg.locator("#daily rect").count())
    pg.locator("#daily").screenshot(path=o + "/ya_daily.png")
    pg.locator("#conn").screenshot(path=o + "/ya_conn.png")
    pg.locator("#vTbl tr.click").first.click(); time.sleep(.7)
    pg.locator("#drawer").screenshot(path=o + "/ya_drawer.png")
    print("오류:", errs, "가로넘침:", pg.evaluate("document.documentElement.scrollWidth>innerWidth"))
    b.close()
