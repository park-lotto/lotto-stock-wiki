import os, time
from playwright.sync_api import sync_playwright
prof = os.path.expanduser("~/.claude/naver_browser_profile")
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(prof, headless=False, channel="chrome", viewport=None)
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto("https://nid.naver.com/nidlogin.login?url=https://cafe.naver.com/f-e/cafes/31786452/menus/24")
    while ctx.pages:
        time.sleep(2)
