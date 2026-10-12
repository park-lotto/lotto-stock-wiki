const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const root = path.resolve(__dirname,'..');
const outDir = path.join(root,'out','assets','scene-style','thumbnails');
const url = process.argv[2] || 'http://127.0.0.1:8770/out/scene-style-ui-showcase.html?revision=47&qa=1';

(async()=>{
  fs.mkdirSync(outDir,{recursive:true});
  const browser=await puppeteer.launch({headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1920,height:1000});
  await page.goto(url,{waitUntil:'networkidle0'});
  await page.addStyleTag({content:'.precision-badge{display:none!important}'});
  const preview=await page.$('#a-live-preview');
  const wait=()=>new Promise(resolve=>setTimeout(resolve,70));

  await page.click('[data-template-mode="continuous"]');
  const fixed=await page.evaluate(()=>window.CONTINUOUS20.map(row=>row.source_id));
  for(let index=0;index<fixed.length;index++){
    await page.click(`[data-p20="${index}"]`);await wait();
    await preview.screenshot({path:path.join(outDir,`fixed-${fixed[index]}.png`)});
  }

  await page.click('[data-template-mode="story"]');
  const story=await page.evaluate(()=>window.PRECISION20.map(row=>row.id));
  for(let index=0;index<story.length;index++){
    await page.click(`[data-p20="${index}"]`);await wait();
    await preview.screenshot({path:path.join(outDir,`story-${story[index]}-hook.png`)});
    await page.click('[data-frame="body"]');await wait();
    await preview.screenshot({path:path.join(outDir,`story-${story[index]}-body.png`)});
    await page.click('[data-frame="hook"]');
  }
  await browser.close();
  console.log(JSON.stringify({fixed:fixed.length,story:story.length,files:fixed.length+story.length*2,outDir},null,2));
})().catch(error=>{console.error(error);process.exit(1)});
