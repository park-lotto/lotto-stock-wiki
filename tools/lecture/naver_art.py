import os, sys, json, time
from playwright.sync_api import sync_playwright
prof = os.path.expanduser("~/.claude/naver_browser_profile")
out, aid = sys.argv[1], sys.argv[2]
reqs=[]
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(prof, headless=True, channel="chrome")
    pg = ctx.new_page()
    pg.on("request", lambda r: reqs.append(r.url) if any(k in r.url for k in ("m3u8",".mp4","vod","play","video","youtube","vimeo","kollus")) else None)
    pg.goto(f"https://cafe.naver.com/f-e/cafes/31786452/articles/{aid}?menuid=24", wait_until="networkidle")
    time.sleep(4)
    frames=[f.url for f in pg.frames]
    txt=""
    for f in pg.frames:
        try:
            t=f.inner_text("body")
            if len(t)>len(txt): txt=t
            for v in f.query_selector_all("video, iframe"):
                frames.append("EL:"+(v.get_attribute("src") or "")+" "+(v.get_attribute("data-src") or ""))
        except Exception: pass
    json.dump({"frames":frames,"reqs":sorted(set(reqs)),"text":txt}, open(f"{out}/art_{aid}.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    ctx.close()
