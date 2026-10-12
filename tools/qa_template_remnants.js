const puppeteer=require('puppeteer'),assert=require('assert'),fs=require('fs');
(async()=>{const browser=await puppeteer.launch({headless:true});try{
 const page=await browser.newPage();await page.setViewport({width:1800,height:1300});const errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
 const dir='.tmp/scene-style-qa/remnants';fs.mkdirSync(dir,{recursive:true});
 await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
 for(const mode of ['story','continuous']){
  await page.click(`[data-template-mode="${mode}"]`);
  for(let i=0;i<20;i++){
   await page.click(`[data-p20="${i}"]`);
   for(const kind of mode==='story'?['hook','body']:['fixed']){
    if(kind!=='fixed')await page.click(`[data-frame="${kind}"]`);
    for(const height of [12,31,50]){
     await page.$eval('[data-fixed-range="top"]',(e,h)=>{e.value=h;e.dispatchEvent(new Event('input',{bubbles:true}))},height);
     await page.evaluate(async()=>{await new Promise(requestAnimationFrame);sceneStyle.motionAt(10000);await Promise.all([...document.querySelectorAll('#a-live-preview img')].map(e=>e.decode().catch(()=>{})));await new Promise(requestAnimationFrame)});
     const state=await page.evaluate(()=>{
      const preview=document.querySelector('#a-live-preview');
      const visibleLegacy=[...preview.querySelectorAll('.brand-row,.shortem-body-channel,.hook-copy,.hook-band,.body-title-area,.body-band,.media-window')].filter(e=>getComputedStyle(e).display!=='none').map(e=>e.className);
      return {visibleLegacy,referenceHidden:getComputedStyle(preview.querySelector('.precision-base')).display==='none',media:sceneStyle.geometry().media,name:document.querySelector('.preset-card.selected b')?.textContent};
     });
     assert.deepEqual(state.visibleLegacy,[],`${mode}/${i}/${kind}/${height}: legacy layers`);
     assert.ok(state.referenceHidden,'baked-in reference pixels excluded');
     assert.ok(Math.abs(state.media.top+state.media.height-100)<.01,'media reaches bottom');
     const file=`${mode}-${String(i).padStart(2,'0')}-${kind}-${height}.png`;
     await(await page.$('#a-live-preview')).screenshot({path:`${dir}/${file}`});results.push({mode,index:i,kind,height,file,...state});
    }
   }
  }
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(`${dir}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify({ok:true,templates:40,views:60,heightScreenshots:results.length}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
