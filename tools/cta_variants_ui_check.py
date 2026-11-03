import sys, json
from playwright.sync_api import sync_playwright
JS = r"""async()=>{
  const posts=[];
  let cfg={tts_mode:'cta',items:[{key:'insta',label:'인스타',on:true,text:'댓글 남겨주세요'},{key:'yt_shop',label:'유튜브 수익창출',on:false,text:'스티커 눌러요'},{key:'yt_long',label:'유튜브 비수창',on:false,text:'관련영상'},{key:'profile',label:'틱톡·클립',on:true,text:'프로필 링크'}]};
  window.fetch=async(u,o)=>{ if(o&&o.method==='POST'){ posts.push(JSON.parse(o.body)); cfg=JSON.parse(o.body); return {json:async()=>({ok:true,config:cfg})}; }
    return {json:async()=>({ok:true,config:cfg,has_cta:true,status:{items:{insta:{status:'done',file:'final_cta_insta.mp4'},profile:{status:'rendering'}}}})}; };
  const box=document.createElement('div'); box.id='ctaVarBox'; box.dataset.job='j1'; document.body.prepend(box);
  await loadCtaVariants();
  const t1=box.innerText;
  const dl=[...box.querySelectorAll('a')].map(a=>a.getAttribute('href'));
  box.querySelectorAll('input[type=checkbox]')[1].click(); await new Promise(r=>setTimeout(r,50));
  box.querySelectorAll('input[type=radio]')[1].click(); await new Promise(r=>setTimeout(r,50));
  clearTimeout(_ctavTimer);
  return {text:t1.slice(0,700), dl, posts:posts.map(p=>[p.tts_mode, p.items.filter(x=>x.on).map(x=>x.key)])};
}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 900, 'height': 900}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file:///' + sys.argv[1]); pg.wait_for_timeout(800)
    r = pg.evaluate(JS)
    pg.locator('#ctaVarBox').screenshot(path=sys.argv[2])
    print(json.dumps(r, ensure_ascii=False, indent=1)); print('errors', [e for e in errs if 'cta' in e.lower() or 'ctav' in e.lower()])
    b.close()
