const puppeteer=require('puppeteer'),assert=require('assert');
(async()=>{const browser=await puppeteer.launch({headless:true});try{
 const page=await browser.newPage();await page.setViewport({width:1800,height:1300});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8768/produce.html',{waitUntil:'networkidle2'});
 await page.evaluate(()=>{MIX_JOB='scene-style-qa';document.querySelector('[data-step="3"]').style.display='block'});
 await page.click('[onclick="openSceneStyleEditor()"]');await page.waitForSelector('dialog[open] iframe');
 const f=await(await page.$('dialog iframe')).contentFrame();await f.waitForFunction(()=>window.sceneStyle?.context()?.jobId);
 await f.evaluate(()=>{sceneStyle.show(2);sceneStyle.effect({zoom:1.5});sceneStyle.show(1)});
 await f.click('.scene-line-editor summary');await f.$eval('[data-line-inputs] input',e=>{e.focus();e.setSelectionRange(3,3)});await page.keyboard.press('Enter');
 assert.equal(await f.$$eval('[data-line-inputs] input',e=>e.length),2);
 await f.$eval('[data-lines-save]',e=>e.scrollIntoView({block:'center'}));await f.click('[data-lines-save]');
 await f.waitForFunction(()=>sceneStyle.context().scenes.length===4,{timeout:15000});
 const packet=await page.evaluate(async()=>await(await fetch('/api/produce/scene-style/context/scene-style-qa')).json());
 assert.equal(packet.context.scenes.length,4);assert.equal(packet.snapshot.effects['3'].zoom,1.5);assert.ok(packet.snapshot.branding.watermark.on);
 await page.screenshot({path:'.tmp/scene-style-qa/lines-server-saved.png'});
 await f.$eval('[data-lines-reset]',e=>e.scrollIntoView({block:'center'}));await f.click('[data-lines-reset]');
 await f.waitForFunction(()=>sceneStyle.context().scenes.length===3,{timeout:15000});assert.equal(await f.evaluate(()=>sceneStyle.snapshot().effects['2'].zoom),1.5);
 if(process.env.QA_LEAVE_SPLIT){await f.$eval('[data-line-inputs] input',e=>{e.focus();e.setSelectionRange(3,3)});await page.keyboard.press('Enter');await f.$eval('[data-lines-save]',e=>e.scrollIntoView({block:'center'}));await f.click('[data-lines-save]');await f.waitForFunction(()=>sceneStyle.context().scenes.length===4);}
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,splitServer:true,autoResetServer:true,sceneSettingsRemapped:true,brandingSaved:true}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
