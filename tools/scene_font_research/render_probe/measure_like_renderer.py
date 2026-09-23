import sys,json,pathlib
from playwright.sync_api import sync_playwright
S=pathlib.Path(sys.argv[1]); tag=sys.argv[2]; req=json.load(open(S/'work_base'/'scene-style-request.json',encoding='utf-8')); snap=req['snapshot']; ctx=req['context']
STYLE="body *{visibility:hidden!important}#a-live-preview,#a-live-preview *{visibility:visible!important}#a-live-preview{position:fixed!important;left:0!important;top:0!important;width:1080px!important;height:1920px!important;max-width:none!important;max-height:none!important;border:0!important;border-radius:0!important;box-shadow:none!important;background:transparent!important;z-index:99999!important}.precision-base,.precision-media,.scene-media-clip,.precision-badge{display:none!important}html,body{background:transparent!important}"
M="""()=>[...document.querySelectorAll('#a-live-preview .precision-text')].map(e=>{const L=document.querySelector('#a-live-preview').getBoundingClientRect();const r=e.getBoundingClientRect();const rg=document.createRange();rg.selectNodeContents(e);const rects=[...rg.getClientRects()];const lines=new Set(rects.map(x=>Math.round(x.top))).size;const ink=rg.getBoundingClientRect();return {bind:e.dataset.editBind,lines,font:parseFloat(getComputedStyle(e).fontSize).toFixed(1),cw:Math.round(e.clientWidth),inkW:Math.round(ink.width),inkLeft:Math.round(ink.left-L.left),inkRight:Math.round(L.right-ink.right),ls:getComputedStyle(e).letterSpacing,tf:e.style.transform||'-',fit:e.dataset.oneLineFit||null}})"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_context(viewport={'width':1920,'height':2200}).new_page()
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1',wait_until='networkidle')
    pg.add_style_tag(content=STYLE); pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)',[ctx,snap])
    pg.evaluate('async()=>{await document.fonts.ready;window.sceneStyle.refresh();window.sceneStyleExporting=true}')
    for i in (1,4,5):
        pg.evaluate(f'()=>window.sceneStyle.show({i})'); pg.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        print(tag,'scene',i,[m for m in pg.evaluate(M) if m['bind'] in ('bodyTitle','hook1','hook2')])
        pg.screenshot(path=str(S/f'renderlike_{tag}_scene{i}.png'),clip={'x':0,'y':0,'width':1080,'height':800})
    b.close()
