const puppeteer=require('puppeteer'),assert=require('assert');
(async()=>{const b=await puppeteer.launch({headless:true});try{const p=await b.newPage();await p.setViewport({width:1800,height:1300});await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});await p.click('[data-editor-tab="effects"]');
 for(const key of ['watermark','ad']){assert.equal(await p.$eval(`[data-brand="${key}"] input[type=checkbox]`,e=>Math.round(e.getBoundingClientRect().width)),18);await p.click(`[data-brand="${key}"] input[type=checkbox]`)}
 let saved=await p.evaluate(()=>sceneStyle.branding());assert.equal(saved.watermark.x,50);assert.equal(saved.ad.x,87);
 const r=await(await p.$('[data-brand-label="watermark"]')).boundingBox();await p.mouse.move(r.x+3,r.y+3);await p.mouse.down();await p.mouse.move(r.x+25,r.y-45,{steps:5});await p.mouse.up();
 await p.$eval('[data-brand="watermark"] [data-brand-field="text"]',e=>{e.value='@remember';e.dispatchEvent(new Event('input',{bubbles:true}))});saved=await p.evaluate(()=>sceneStyle.branding());
 await p.reload({waitUntil:'networkidle0'});assert.deepEqual(await p.evaluate(()=>sceneStyle.branding()),saved);
 await p.evaluate(()=>sceneStyle.load({jobId:'another',text:{},scenes:[{kind:'body',beat_idx:0,caption:'test'}]},{branding:{}}));assert.deepEqual(await p.evaluate(()=>sceneStyle.branding()),saved);
 await p.click('[data-editor-tab="effects"]');await p.click('[data-brand="watermark"] [data-brand-reset]');assert.equal(await p.evaluate(()=>sceneStyle.branding().watermark.x),50);
 await p.screenshot({path:'.tmp/scene-style-qa/branding-memory.png'});console.log(JSON.stringify({ok:true,checkboxLayout:true,defaultPositions:true,autoRemember:true,newJob:true,resetPosition:true}));
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
