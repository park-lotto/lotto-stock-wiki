const puppeteer=require('puppeteer'),path=require('path');
(async()=>{
 const browser=await puppeteer.launch({headless:true});const page=await browser.newPage();const failures=[];
 await page.setViewport({width:1920,height:1000});page.on('pageerror',e=>failures.push(e.message));
 const url='http://127.0.0.1:8767/out/scene-style-ui-showcase.html';
 await page.goto(url+'?qa=1&frame=body',{waitUntil:'networkidle0'});
 const settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 let count=0;
 for(const mode of ['story','continuous']){
  await page.click(`[data-template-mode="${mode}"]`);
  const rows=await page.evaluate(mode=>(mode==='story'?window.PRECISION20:window.CONTINUOUS20).map(p=>p.id),mode);
  for(let i=0;i<(process.argv.includes('--quick')?1:rows.length);i++){
   await page.click(`[data-p20="${i}"]`);
   if(mode==='story')await page.click('[data-frame="body"]');
   else {await page.evaluate(()=>{while(Number(document.querySelector('[data-scene-current]').textContent)>1)document.querySelector('[data-scene-step="-1"]').click();});await page.click('[data-scene-step="1"]');}
   await settle();
   const input=await page.$('.layout-a [data-bind="caption"]');
   await input.click();await page.keyboard.down('Control');await page.keyboard.press('KeyA');await page.keyboard.up('Control');await input.type('첫 장면 자막 테스트');
   const selector='.precision-text[data-edit-bind="caption"]';
   const text=await page.$eval(selector,e=>e.textContent);if(text!=='첫 장면 자막 테스트')failures.push(rows[i]+': 입력 실패 '+JSON.stringify(text));
   const font=await page.$eval(selector,e=>parseFloat(e.style.fontSize));
   await page.click('[data-field-key="caption"] [data-font-step="0.1"]');await settle();
   const larger=await page.$eval(selector,e=>parseFloat(e.style.fontSize));if(larger<=font)failures.push(rows[i]+': 크기 증가 실패');
   const el=await page.$(selector),box=await el.boundingBox();
   await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2,box.y+box.height/2-30,{steps:8});await page.mouse.up();await settle();
   const moved=await (await page.$(selector)).boundingBox();if(Math.abs(moved.y-box.y+30)>3)failures.push(rows[i]+': 드래그 실패 '+(moved.y-box.y));
   await page.click('[data-scene-step="1"]');
   await input.click();await page.keyboard.down('Control');await page.keyboard.press('KeyA');await page.keyboard.up('Control');await input.type('다음 장면은 다른 문구');await page.click('[data-scene-step="-1"]');
   if(await page.$eval(selector,e=>e.textContent)!=='첫 장면 자막 테스트')failures.push(rows[i]+': 장면별 문구 유실');
   const back=await (await page.$(selector)).boundingBox();if(Math.abs(back.y-moved.y)>3)failures.push(rows[i]+': 위치 유실');
   if(mode==='story'){
    if(!await page.$eval('.precision-base',e=>e.hidden))failures.push(rows[i]+': 원본 배경 노출');
    if(await page.$('.body-ornament-rule,.body-ornament-bookmark'))failures.push(rows[i]+': 잔여 장식');
   }
   count++;
  }
 }
 await page.click('[data-template-mode="story"]');await page.click('[data-p20="14"]');await page.click('[data-frame="body"]');
 await page.$eval('[data-bind="caption"]',e=>{e.value='저장한 자막 유지';e.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.click('.layout-a .secondary');await page.goto(url+'?frame=body',{waitUntil:'networkidle0'});
 if(await page.$eval('.precision-text[data-edit-bind="caption"]',e=>e.textContent)!=='저장한 자막 유지')failures.push('새로고침 복원 실패');
 await (await page.$('#a-live-preview')).screenshot({path:path.join(process.env.TEMP,'caption-fixed.png')});
 await browser.close();console.log(JSON.stringify({count,failures},null,2));process.exitCode=failures.length?1:0;
})().catch(e=>{console.error(e);process.exit(1)});
