const puppeteer=require('puppeteer'),assert=require('assert'),fs=require('fs');
(async()=>{const browser=await puppeteer.launch({headless:true});try{
 const page=await browser.newPage();await page.setViewport({width:1800,height:1300});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
 await page.click('[data-frame="body"]');
 const inspect=()=>page.evaluate(()=>({media:sceneStyle.geometry().media,mask:(()=>{const e=document.querySelector('.caption-mask');return {top:e.style.top,left:e.style.left,height:e.style.height,bg:e.style.background}})(),paints:[...document.querySelectorAll('.body-material')].map(e=>e.style.background)}));
 for(let i=0;i<20;i++){
  await page.click(`[data-p20="${i}"]`);await page.click('[data-frame="body"]');
  const before=await inspect();await page.click('[data-caption-placement="free"]');
  const after=await inspect();assert.deepEqual(before.paints,after.paints,'template colors '+i);assert.equal(Math.round(after.media.top+after.media.height),100);
  assert.ok(before.media.top>after.media.top,'title band releases space '+i);
 }
 await page.click('[data-p20="0"]');await page.click('[data-frame="body"]');
 await page.click('[data-caption-placement="free"]');
 await page.$eval('[data-caption-layout="w"]',e=>{e.value='80';e.dispatchEvent(new Event('input',{bubbles:true}))});
 await page.$eval('[data-caption-layout="h"]',e=>{e.value='12';e.dispatchEvent(new Event('input',{bubbles:true}))});
 await page.$eval('[data-bind="caption"]',e=>{e.value='원본 자막 자국을\n이 자리에서 덮어요';e.dispatchEvent(new Event('input',{bubbles:true}))});
 const mask=await(await page.$('.caption-mask')).boundingBox();await page.mouse.move(mask.x+5,mask.y+5);await page.mouse.down();await page.mouse.move(mask.x+25,mask.y+155,{steps:8});await page.mouse.up();
 const moved=await inspect();assert.ok(parseFloat(moved.mask.top)>40,'drag background with caption');
 const snap=await page.evaluate(()=>sceneStyle.snapshot());
 await page.click('.layout-a .edit-pane > .primary');await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
 assert.deepEqual(await page.evaluate(()=>sceneStyle.snapshot().captionLayouts),snap.captionLayouts);assert.deepEqual(await page.evaluate(()=>sceneStyle.snapshot().captionDrags),snap.captionDrags);
 assert.deepEqual((await inspect()).mask,moved.mask);
 await page.screenshot({path:'.tmp/scene-style-qa/caption-free.png'});
 fs.writeFileSync('.tmp/scene-style-qa/caption-placement-snapshot.json',JSON.stringify(await page.evaluate(()=>sceneStyle.snapshot())));
 await page.click('[data-caption-placement="title"]');const pinned=await inspect();assert.ok(parseFloat(pinned.mask.top)<parseFloat(moved.mask.top));
 await page.screenshot({path:'.tmp/scene-style-qa/caption-title.png'});
 await page.click('[data-template-mode="continuous"]');
 for(let i=0;i<20;i++){
  await page.click(`[data-p20="${i}"]`);await page.click('[data-caption-placement="title"]');const before=await inspect();
  await page.click('[data-caption-placement="free"]');const after=await inspect();assert.ok(before.media.top>after.media.top);assert.equal(Math.round(after.media.top+after.media.height),100);
 }
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,templates:40,colorsPreserved:true,maskDragRestore:true,noFooter:true}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
