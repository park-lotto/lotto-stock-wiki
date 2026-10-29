// 관리자 전용 틀(template_register.py admin_only) 노출 검사 — 장면꾸미기 화면(그대로)을 열어 고정형 목록 카드를 센다.
//   context.adminView=false(고객) → 칼카피 카드 0개 · 전체 개수는 등록 전과 같음 / true(관리자) → 등록한 틀 카드가 보인다.
//   쓰는 법: node tools/calcopy/check_admin_templates.js   (출력 JSON, 실패면 종료 코드 1)
const path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
(async()=>{
  const browser=await puppeteer.launch({headless:true,args:process.env.SCENE_STYLE_NO_SANDBOX==='1'?['--no-sandbox']:[]});
  const out={};
  try{
    for(const admin of [false,true]){
      const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.goto(pathToFileURL(path.resolve(__dirname,'../../out/scene-style-ui-showcase.html')).href+'?qa=1',{waitUntil:'networkidle0'});
      const before=await page.evaluate(()=>document.querySelector('.layout-a .pane-head .count')?.textContent||'');
      await page.evaluate(a=>window.sceneStyle.load({adminView:a,scenes:[{start:0,end:3,caption:'자막'}]},null),admin);
      await page.evaluate(()=>document.querySelector('[data-template-mode="continuous"]')?.click());
      await new Promise(r=>setTimeout(r,300));
      const r=await page.evaluate(()=>{const names=[...document.querySelectorAll('.preset-card b')].map(b=>b.textContent);
        const rows=(window.CONTINUOUS20||[]);return {cards:names.length,calcopy:names.filter(n=>n.startsWith('칼카피')),
          adminRows:rows.filter(p=>p.admin_only).map(p=>p.name),count:document.querySelector('.layout-a .pane-head .count')?.textContent||''}});
      out[admin?'admin':'customer']={...r,countBeforeLoad:before,errors};
      await page.close();
    }
  }finally{await browser.close()}
  const c=out.customer,a=out.admin;
  const ok=c.calcopy.length===0&&a.calcopy.length===a.adminRows.length&&a.adminRows.length>0&&c.errors.length===0&&a.errors.length===0
    &&a.cards-c.cards===a.adminRows.length;
  console.log(JSON.stringify({ok,...out},null,1));
  process.exit(ok?0:1);
})().catch(e=>{console.error(e);process.exit(1)});
