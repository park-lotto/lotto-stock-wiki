const puppeteer = require('puppeteer');
const path = require('path');

const url = process.argv[2] || 'http://127.0.0.1:8770/out/scene-style-ui-showcase.html?revision=45&qa=1';
(async () => {
  const browser = await puppeteer.launch({headless:true});
  const page = await browser.newPage();
  await page.setViewport({width:1920,height:1000});
  await page.goto(url,{waitUntil:'networkidle0'});
  await page.click('[data-template-mode="story"]');
  const rows = await page.evaluate(()=>window.PRECISION20.map(row=>({id:row.id,name:row.name})));
  for(let index=0;index<rows.length;index++){
    await page.click(`[data-p20="${index}"]`);
    await new Promise(resolve=>setTimeout(resolve,60));
    await (await page.$('#a-live-preview')).screenshot({path:path.join(process.env.TEMP,`cleanup-story-${String(index).padStart(2,'0')}-${rows[index].id}.png`)});
  }
  console.log(JSON.stringify({count:rows.length,folder:process.env.TEMP},null,2));
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
