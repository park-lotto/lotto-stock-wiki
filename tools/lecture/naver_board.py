import os, sys, json, time
from playwright.sync_api import sync_playwright
prof = os.path.expanduser("~/.claude/naver_browser_profile")
out = sys.argv[1]
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(prof, headless=True, channel="chrome")
    pg = ctx.new_page()
    pg.goto("https://cafe.naver.com/f-e/cafes/31786452/menus/24", wait_until="networkidle")
    time.sleep(3)
    pg.screenshot(path=out+"/board.png")
    links = pg.eval_on_selector_all("a[href*='articles']", "els=>els.map(e=>[e.innerText.trim(),e.href])")
    json.dump({"url":pg.url,"title":pg.title(),"links":links,"text":pg.inner_text("body")[:3000]}, open(out+"/board.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    ctx.close()
