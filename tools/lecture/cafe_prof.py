# 강의 작업 전용 네이버 프로필(다른 세션의 google_browser_profile 과 분리)
import os, sys, io, json, time
from contextlib import contextmanager
from playwright.sync_api import sync_playwright
PROFILE = os.path.expanduser(r"~\.claude\cafe_lecture_profile")
CLUB = 31786452
@contextmanager
def page(headless=False):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=headless, viewport=None,
            ignore_default_args=["--enable-automation"], args=["--disable-blink-features=AutomationControlled"])
        try: yield ctx.pages[0] if ctx.pages else ctx.new_page()
        finally: ctx.close()
def naver_in(pg):
    return any(c["name"] == "NID_AUT" for c in pg.context.cookies("https://naver.com"))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    OUT = sys.argv[1]
    with page() as pg:
        pg.goto(f"https://cafe.naver.com/f-e/cafes/{CLUB}/menus/0"); time.sleep(3)
        if not naver_in(pg):
            pg.goto("https://nid.naver.com/nidlogin.login?url=https://cafe.naver.com/")
            print("로그인 대기", flush=True)
            for _ in range(450):
                if naver_in(pg): break
                time.sleep(2)
        print("네이버 로그인:", naver_in(pg))
        pg.goto(f"https://cafe.naver.com/f-e/cafes/{CLUB}/menus/0"); time.sleep(3)
        r = pg.request.get(f"https://apis.naver.com/cafe-web/cafe2/SideMenuList?cafeId={CLUB}")
        d = r.json(); json.dump(d, open(OUT + "/menus_raw.json", "w", encoding="utf-8"), ensure_ascii=False)
        for m in d.get("message", {}).get("result", {}).get("menus", []): print(m.get("menuId"), m.get("menuName"))
