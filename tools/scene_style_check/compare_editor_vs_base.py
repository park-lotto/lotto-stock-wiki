"""장면꾸미기 편집기: 기준 커밋(어제) vs 지금, 20템플릿×흰띠모션×장면 픽셀 대조. 사용: (트랙 루트에서) git show <기준>:out/precision20-ui.js > out/_cmp_old_ui.js 등 3파일 만든 뒤
py tools/scene_style_check/compare_editor_vs_base.py <ctx json 폴더>  — ctx는 서버 context_for 출력(real29.json). 10-02 관제 058: 어제와 다른 칸 0/126 확인용."""
from playwright.sync_api import sync_playwright
import pathlib, json, sys
from PIL import Image, ImageChops
S=sys.argv[1]; ctx=json.load(open(S+"/real29.json",encoding="utf-8"))["ctx"]
ids=[r["id"] for r in json.loads(open("out/precision20-data.js",encoding="utf-8-sig").read().strip().split("=",1)[1].rstrip(";\r\n "))]
with sync_playwright() as p:
    b=p.chromium.launch(); pages={}
    for ver,fn in (("old","_cmp_old.html"),("new","scene-style-ui-showcase.html")):
        pg=b.new_page(viewport={"width":1500,"height":900}); pg.goto(pathlib.Path("out/"+fn).resolve().as_uri(), wait_until="domcontentloaded"); pg.wait_for_timeout(2500); pages[ver]=pg
    bad=[]; tot=0
    for pid in ids:
        for motion in ("","rise"):
            for idx in (0,1,2):
                tot+=1
                for ver,pg in pages.items():
                    snap=pg.evaluate("()=>window.sceneStyle.snapshot()"); snap.update({"presetId":pid,"mode":"story","hookBandMotion":motion,"hookMotion":"none"})
                    pg.evaluate("(a)=>window.sceneStyle.load(a[0],a[1])",[ctx,snap]); pg.evaluate(f"()=>window.sceneStyle.show({idx})"); pg.wait_for_timeout(2200)
                    pg.locator("#a-live-preview").screenshot(path=f"{S}/p_{ver}.png")
                d=ImageChops.difference(Image.open(f"{S}/p_old.png").convert("RGB"),Image.open(f"{S}/p_new.png").convert("RGB"))
                n=sum(1 for v in d.convert("L").getdata() if v>40)
                if n>200: bad.append((pid,motion,idx,n)); Image.open(f"{S}/p_old.png").save(f"{S}/bad_old.png"); Image.open(f"{S}/p_new.png").save(f"{S}/bad_new.png")
    print("어제와 다른 칸:", bad[:8], "개수", len(bad), "/ 전체", tot); b.close()
