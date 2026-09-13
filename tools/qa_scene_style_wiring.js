// Read/write audit against the isolated QA job; never use a customer job.
const puppeteer=require('puppeteer'),fs=require('fs');
(async()=>{
 const browser=await puppeteer.launch({headless:true});
 const origin='http://127.0.0.1:8768',url=origin+'/api/produce/scene-style/context/scene-style-qa';
 const original=await(await fetch(url)).json();
 try{
  const page=await browser.newPage();await page.setViewport({width:1800,height:1200});
  await page.goto(origin+'/produce.html',{waitUntil:'networkidle2'});
  await page.evaluate(()=>{MIX_JOB='scene-style-qa'});
  const open=async()=>{
   await page.evaluate(()=>openSceneStyleEditor());await page.waitForSelector('dialog[open] iframe');
   let frame=await(await page.$('dialog iframe')).contentFrame();
   await frame.waitForFunction(()=>window.sceneStyle?.context()?.jobId);
   return frame;
  };
  let frame=await open();
  const baseline=await frame.evaluate(()=>{
   sceneStyle.show(2);sceneStyle.effect({...sceneStyle.effect(),zoom:1.65,panX:.3});
   return sceneStyle.snapshot();
  });
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/produce/mix/settings')&&r.request().method()==='POST');
  await frame.evaluate(()=>parent.postMessage({type:'scene-style-save',jobId:'scene-style-qa',snapshot:sceneStyle.snapshot()},location.origin));
  await saved;await page.waitForFunction(()=>document.getElementById('sceneStyleStatus').textContent.includes('적용됨'));
  await page.evaluate(()=>document.querySelector('dialog').close());frame=await open();
  const reopened=await frame.evaluate(()=>sceneStyle.snapshot());
  await frame.evaluate(()=>{sceneStyle.show(2);sceneStyle.effect({...sceneStyle.effect(),zoom:1.91});});
  await page.evaluate(()=>document.querySelector('dialog').close());frame=await open();
  const unsaved=await frame.evaluate(()=>sceneStyle.snapshot());
  const stored=await(await fetch(url)).json();
  await page.reload({waitUntil:'networkidle2'});
  await page.evaluate(()=>{MIX_JOB='scene-style-qa'});frame=await open();
  const reloaded=await frame.evaluate(()=>sceneStyle.snapshot());
  const result={savedScene:baseline.sceneIndex,reopenedScene:reopened.sceneIndex,
   savedEffect:baseline.effects['2'],reopenedEffect:reopened.effects['2'],
   unsavedZoom:1.91,afterCloseZoom:unsaved.effects['2'].zoom,serverEffect:stored.snapshot.effects['2'],
   reloadedScene:reloaded.sceneIndex,reloadedEffect:reloaded.effects['2']};
  await page.screenshot({path:'.tmp/scene-style-qa/wiring-reopen.png'});
  fs.writeFileSync('.tmp/scene-style-qa/wiring-audit.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 }finally{
  await fetch(origin+'/api/produce/mix/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:'scene-style-qa',deco:{scene_style:original.snapshot}})});
  await browser.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1});
