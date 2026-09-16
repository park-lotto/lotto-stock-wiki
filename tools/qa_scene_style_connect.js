const puppeteer=require('puppeteer'),fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const out=path.resolve(process.argv[2]||'.tmp/scene-style-qa');fs.mkdirSync(out,{recursive:true});
 const browser=await puppeteer.launch({headless:true});
 try{
  const page=await browser.newPage();await page.setViewport({width:1800,height:1050});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
  assert.deepEqual(await page.$$eval('.layout-a .tool-tabs button',els=>els.map(e=>e.textContent)),['문구/텍스트','효과']);
  const context={jobId:'qa',text:{channel:'숏템메이커',hook1:'청소가 쉬워지는',hook2:'생활 아이디어',bodyTitle:'한 번에 깨끗하게'},scenes:[{caption:'첫 번째 실제 자막',kind:'hook'},{caption:'두 번째 실제 자막',kind:'body'},{caption:'마지막 실제 자막',kind:'body'}]};
  await page.evaluate(c=>{const s=window.sceneStyle.snapshot();s.mode='continuous';s.presetId=window.CONTINUOUS20[0].id;window.sceneStyle.load(c,s)},context);
  assert.equal(await page.$eval('[data-bind="caption"]',e=>e.value),'첫 번째 실제 자막');
  await page.click('[data-editor-tab="effects"]');await page.click('[data-effect-mode="spot"]');
  await page.$eval('[data-effect="zoom"]',e=>{e.value=1.35;e.dispatchEvent(new Event('input',{bubbles:true}))});
  assert.equal((await page.evaluate(()=>window.sceneStyle.snapshot())).effects['0'].zoom,1.35);
  await page.screenshot({path:path.join(out,'effects-ui.png')});
  await page.click('[data-scene-step="1"]');assert.equal(await page.$eval('[data-bind="caption"]',e=>e.value),'두 번째 실제 자막');
  await page.click('[data-effect-mode="zoom"]');
  await page.click('[data-editor-tab="text"]');
  await page.$eval('[data-bind="caption"]',e=>{e.value='직접 고친 두 번째 자막';e.dispatchEvent(new Event('input',{bubbles:true}))});
  await page.click('[data-scene-step="-1"]');await page.click('[data-scene-step="1"]');
  assert.equal(await page.$eval('[data-bind="caption"]',e=>e.value),'직접 고친 두 번째 자막');
  await page.click('.layout-a .edit-pane > .primary');
  const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('scene_style_preset')));
  fs.writeFileSync(path.join(out,'snapshot.json'),JSON.stringify(saved));
  await page.screenshot({path:path.join(out,'text-ui.png')});
  assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,scenes:3,tabs:2,effects:saved.effects,out}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
