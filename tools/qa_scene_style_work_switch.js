const puppeteer=require('puppeteer'),assert=require('assert');
(async()=>{
 const browser=await puppeteer.launch({headless:true});
 try{
  const page=await browser.newPage();await page.setViewport({width:1800,height:1200});
  const open=async work=>{
   await page.goto('http://127.0.0.1:8768/produce?work='+work,{waitUntil:'networkidle2'});
   await page.waitForFunction(()=>typeof MIX_JOB!=='undefined'&&MIX_JOB);
   await page.evaluate(()=>openSceneStyleEditor());await page.waitForSelector('dialog[open] iframe');
   const frame=await(await page.$('dialog iframe')).contentFrame();
   await frame.waitForFunction(()=>window.sceneStyle?.context()?.jobId);
   await frame.waitForFunction(()=>{const img=document.querySelector('.precision-media');return img?.complete&&img.naturalWidth>0});
   return frame;
  };
  let frame=await open('qa-work-a');
  assert.equal(await frame.evaluate(()=>sceneStyle.context().jobId),'scene-style-qa-a');
  assert.equal(await frame.evaluate(()=>sceneStyle.snapshot().effects['1'].zoom),1.21);
  await frame.evaluate(()=>{sceneStyle.show(1);sceneStyle.effect({zoom:1.43,panX:-.2})});
  await page.click('dialog > div button');await page.waitForSelector('dialog[open]',{hidden:true});

  frame=await open('qa-work-b');
  assert.equal(await frame.evaluate(()=>sceneStyle.context().jobId),'scene-style-qa-b');
  assert.equal(await frame.evaluate(()=>sceneStyle.snapshot().effects['2'].zoom),1.72);
  await page.click('dialog > div button');await page.waitForSelector('dialog[open]',{hidden:true});

  frame=await open('qa-work-a');
  const restored=await frame.evaluate(()=>sceneStyle.snapshot());
  assert.equal(restored.sceneIndex,1);assert.equal(restored.effects['1'].zoom,1.43);assert.equal(restored.effects['1'].panX,-.2);
  console.log(JSON.stringify({ok:true,a:restored.effects['1'],sceneIndex:restored.sceneIndex,bKept:true}));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
