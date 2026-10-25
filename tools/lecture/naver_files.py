import os, sys, json, time
from playwright.sync_api import sync_playwright
prof = os.path.expanduser("~/.claude/naver_browser_profile")
out = sys.argv[1]; res={}
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(prof, headless=True, channel="chrome")
    pg = ctx.new_page()
    for aid in ["1323","1324","1325","1331","1332","1349"]:
        pg.goto(f"https://cafe.naver.com/ca-fe/cafes/31786452/articles/{aid}?menuid=24", wait_until="networkidle"); time.sleep(3)
        best=None
        for f in pg.frames:
            try:
                el=f.query_selector(".se-main-container, .ContentRenderer, .article_viewer")
                if el: best=f; break
            except Exception: pass
        f=best or pg.main_frame
        body=""
        try: body=f.inner_text(".se-main-container, .ContentRenderer, .article_viewer")
        except Exception: pass
        links=f.eval_on_selector_all("a", "els=>els.map(e=>[e.innerText.trim().slice(0,80),e.href]).filter(x=>/file|down|attach|drive|canva|docs|\.pdf|\.ppt|\.zip/i.test(x[0]+x[1]))")
        imgs=f.eval_on_selector_all(".se-main-container img, .article_viewer img","els=>els.map(e=>e.src)")
        res[aid]={"body":body,"links":links,"imgs":imgs}
    json.dump(res, open(out+"/files.json","w",encoding="utf-8"), ensure_ascii=False, indent=1); ctx.close()
