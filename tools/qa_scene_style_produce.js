const puppeteer=require('puppeteer'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await puppeteer.launch({headless:true});
 try{
  const page=await browser.newPage();await page.setViewport({width:1800,height:1050});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8768/produce.html',{waitUntil:'networkidle2',timeout:60000});
  await page.evaluate(()=>{MIX_JOB='scene-style-qa';document.querySelector('[data-step="3"]').style.display='block'});
  await page.$eval('[onclick="openSceneStyleEditor()"]',e=>e.scrollIntoView());
  await page.click('[onclick="openSceneStyleEditor()"]');
  await page.waitForSelector('dialog[open] iframe');
  const frame=await (await page.$('dialog[open] iframe')).contentFrame();
  await frame.waitForFunction(()=>document.querySelector('[data-connection-status]')?.textContent.includes('연결했습니다'));
  assert.equal(await frame.$eval('[data-scene-total]',e=>e.textContent),'3');
  await frame.click('[data-editor-tab="effects"]');await frame.click('[data-effect-mode="zoom"]');
  await frame.click('.layout-a .edit-pane > .primary');
  await frame.waitForFunction(()=>document.querySelector('.layout-a .primary').textContent.includes('적용됨'));
  const saved=await page.evaluate(async()=>await(await fetch('/api/produce/scene-style/context/scene-style-qa')).json());
  assert.equal(saved.snapshot.effects['0'].highlight.mode,'zoom');
  await page.screenshot({path:path.resolve('.tmp/scene-style-qa/produce-connected.png')});
  console.log(JSON.stringify({ok:true,serverSave:true,scenes:3,pageErrors:errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
