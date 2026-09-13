const puppeteer=require('puppeteer'),assert=require('assert'),fs=require('fs');
const luminance=c=>{const v=(c.match(/\d+/g)||[]).slice(0,3).map(Number).map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);return v[0]*.2126+v[1]*.7152+v[2]*.0722};
const contrast=(a,b)=>{a=luminance(a);b=luminance(b);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
(async()=>{const b=await puppeteer.launch({headless:true});try{
 const p=await b.newPage();await p.setViewport({width:1800,height:1300});const errors=[],results=[];p.on('pageerror',e=>errors.push(e.message));const dir='.tmp/scene-style-qa/body-palettes';fs.mkdirSync(dir,{recursive:true});
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
 for(let i=0;i<20;i++){
  await p.click(`[data-p20="${i}"]`);await p.click('[data-frame="body"]');
  for(const palette of ['original','mint','yellow','pink']){
   await p.click(`[data-fixed-palette="${palette}"]`);await p.evaluate(async()=>{await new Promise(requestAnimationFrame);sceneStyle.motionAt(10000)});
   const colors=await p.evaluate(()=>{const layer=document.querySelector('.precision-edit-layer');return {background:getComputedStyle(layer.querySelector('.body-material')).backgroundColor,texts:[...layer.querySelectorAll('.precision-text:not([data-edit-bind="caption"])')].map(e=>({bind:e.dataset.editBind,color:getComputedStyle(e).color})),ornaments:[...layer.querySelectorAll('.body-ornament')].map(e=>getComputedStyle(e).color)}});
   if(palette!=='original'){
    for(const text of colors.texts)assert.ok(contrast(text.color,colors.background)>=4.5,`${i}/${palette}/${text.bind} contrast`);
    for(const color of colors.ornaments)assert.ok(contrast(color,colors.background)>=3,`${i}/${palette} ornament contrast`);
   }
   await(await p.$('#a-live-preview')).screenshot({path:`${dir}/${String(i).padStart(2,'0')}-${palette}.png`});results.push({i,palette,...colors});
  }
  await p.$eval('[data-fixed-color="channel"]',e=>{e.value='#ffcc88';e.dispatchEvent(new Event('input',{bubbles:true}))});
  assert.equal(await p.$eval('.precision-text[data-edit-bind="channel"]',e=>getComputedStyle(e).color),'rgb(255, 204, 136)');
 }
 await p.click('.layout-a .edit-pane > .primary');const before=await p.evaluate(()=>sceneStyle.snapshot().fixedColors);
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});assert.deepEqual(await p.evaluate(()=>sceneStyle.snapshot().fixedColors),before);
 assert.equal(await p.$eval('.precision-text[data-edit-bind="channel"]',e=>getComputedStyle(e).color),'rgb(255, 204, 136)');
 assert.deepEqual(errors,[]);fs.writeFileSync(`${dir}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify({ok:true,bodyTemplates:20,paletteScreens:80,contrast:true,channelPicker:20,savedRestore:true}));
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
