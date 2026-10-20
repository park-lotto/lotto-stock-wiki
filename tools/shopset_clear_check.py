"""장면꾸미기 쇼핑 안내 세트 빼기 점검(2026-10-18 고객 제보 B3). 사용: py tools/shopset_clear_check.py <scene-style-ui-showcase.html 절대경로> <scene_style JSON(effects.24.masks 포함)>"""
import sys,json
from playwright.sync_api import sync_playwright
page,ssf=sys.argv[1],sys.argv[2]
ss=json.load(open(ssf,encoding='utf-8'))
masks=ss["effects"]["24"]["masks"]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1400,'height':1000})
    errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file:///'+page); pg.wait_for_timeout(2500)
    r=pg.evaluate("""(masks)=>{
      const api=window.sceneStyle; if(!api) return 'no api';
      const n=api.sceneCount?.()||0; const i=Math.min(3,n-1);
      api.effectAt(i,{...api.effectAt(i),masks:masks.map(m=>({...m}))});
      const before=api.effectAt(i).masks.length;
      const btn=document.querySelector('[data-shopset=clear]'); if(!btn) return 'no btn';
      btn.click();
      const left=api.effectAt(i).masks.map(m=>(m.graphic||m.text||m.kind));
      return {scenes:n, before, after:left.length, left};
    }""", masks)
    print(json.dumps(r,ensure_ascii=False)); print('errors',errs[:3]); b.close()
