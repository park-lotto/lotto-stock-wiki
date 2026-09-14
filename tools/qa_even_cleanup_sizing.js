const puppeteer=require('puppeteer'),path=require('path'),fs=require('fs');
(async()=>{
 const browser=await puppeteer.launch({headless:true}),page=await browser.newPage(),errors=[];
 await page.setViewport({width:1920,height:1000});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1&revision=54',{waitUntil:'networkidle0'});
 await page.evaluate(()=>document.fonts.ready);
 if(await page.evaluate(()=>window.PRECISION20[0].id)!=='t11')errors.push('이븐쇼핑 첫 순서 아님');
 for(const kind of ['hook','body']){
  await page.click(`[data-frame="${kind}"]`);
  await (await page.$('#a-live-preview')).screenshot({path:path.join(process.env.TEMP,`even-${kind}-v54.png`)});
 }
 const ids=await page.evaluate(()=>window.PRECISION20.map(p=>p.id));
 for(let i=0;i<ids.length;i++){
  await page.click(`[data-p20="${i}"]`);
  for(const kind of ['hook','body']){
   await page.click(`[data-frame="${kind}"]`);
   const issues=await page.evaluate(({i,kind})=>{
    const p=window.PRECISION20[i],f=p[kind],issues=[];
    if(f.white_box&&!f.white_box.text)issues.push('빈 흰띠');
    if(f.cleanup_regions.some(r=>r.role==='source-footer'))issues.push('빈 하단바');
    if((f.surfaces||[]).some(s=>s.width===2))issues.push('자막 세로선');
    const m=document.querySelector('.precision-media').getBoundingClientRect(),b=document.querySelector('#a-live-preview').getBoundingClientRect();
    if(Math.abs(b.bottom-m.bottom)>2)issues.push('영상이 바닥에 안 닿음');
    return issues;
   },{i,kind});errors.push(...issues.map(e=>`${ids[i]}/${kind}: ${e}`));
   if(process.argv.includes('--thumbnails')){
    const image=await (await page.$('#a-live-preview')).screenshot();
    fs.writeFileSync(path.resolve(__dirname,`../out/assets/scene-style/thumbnails/story-${ids[i]}-${kind}.png`),image);
   }
  }
 }
 await page.click('[data-template-mode="continuous"]');
 const measurements=[];
 const selector='.precision-text[data-edit-bind="hook1"]';
 for(let i=0;i<10;i++){
  measurements.push(await page.$eval(selector,e=>({font:parseFloat(e.style.fontSize),transform:getComputedStyle(e).transform,width:e.getBoundingClientRect().width})));
  await page.click('[data-field-key="hook1"] [data-font-step="0.1"]');
 }
 for(let i=2;i<measurements.length;i++)if(measurements[i].font<=measurements[i-1].font||measurements[i].transform!=='none')errors.push('수동 크기 자동축소 '+i);
 await page.screenshot({path:path.join(process.env.TEMP,'fixed-size-v54.png')});
 await browser.close();console.log(JSON.stringify({frames:ids.length*2,measurements,errors},null,2));process.exitCode=errors.length?1:0;
})().catch(e=>{console.error(e);process.exit(1)});
