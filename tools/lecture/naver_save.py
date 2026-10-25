import os, sys, json
from playwright.sync_api import sync_playwright
prof = os.path.expanduser("~/.claude/naver_browser_profile")
S, D = sys.argv[1], sys.argv[2]
d=json.load(open(S+"/files.json",encoding="utf-8"))
open(D+"/1332_타임라인.txt","w",encoding="utf-8").write(d["1332"]["body"])
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(prof, headless=True, channel="chrome")
    pg=ctx.new_page(); pg.goto("https://cafe.naver.com/ca-fe/cafes/31786452/articles/1323?menuid=24")
    r=ctx.request.get(d["1323"]["links"][0][1], headers={"Referer":"https://cafe.naver.com/"})
    cd=r.headers.get("content-disposition",""); print(r.status, cd[:150], len(r.body()))
    open(D+"/3주차_발표자료.pdf","wb").write(r.body())
    os.makedirs(D+"/1349_요약이미지",exist_ok=True)
    for i,u in enumerate(d["1349"]["imgs"]):
        b=ctx.request.get(u, headers={"Referer":"https://cafe.naver.com/"}).body()
        open(f"{D}/1349_요약이미지/{i+1:02d}.jpg","wb").write(b)
    ctx.close()
