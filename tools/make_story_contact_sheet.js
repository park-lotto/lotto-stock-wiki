const puppeteer=require('puppeteer');
const path=require('path');
const fs=require('fs');

(async()=>{
  const browser=await puppeteer.launch({headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1320,height:2200,deviceScaleFactor:1});
  await page.goto('http://127.0.0.1:8770/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
  const rows=await page.evaluate(()=>window.PRECISION20.map(row=>row.id));
  const cards=[];
  for(let index=0;index<rows.length;index++){
    const kind='hook';
    const file=path.join(process.env.TEMP,`cleanup-story-${String(index).padStart(2,'0')}-${rows[index]}.png`);
    if(!fs.existsSync(file))continue;
    const image=`data:image/png;base64,${fs.readFileSync(file).toString('base64')}`;
    cards.push(`<div class="card"><img src="${image}"><b>${index+1} · ${rows[index]} · ${kind}</b></div>`);
  }
  await page.setContent(`<style>body{margin:0;padding:20px;background:#07131d;color:white;font:13px sans-serif}.grid{display:grid;grid-template-columns:repeat(8,1fr);gap:13px}.card{display:grid;gap:4px;text-align:center}.card img{width:145px;height:258px;object-fit:contain;background:#000;border:1px solid #35505b}</style><div class="grid">${cards.join('')}</div>`,{waitUntil:'domcontentloaded',timeout:0});
  await page.evaluate(()=>Promise.all([...document.images].map(img=>img.complete?Promise.resolve():new Promise(resolve=>{img.onload=img.onerror=resolve}))));
  const output=path.join(process.env.TEMP,'story40-contact-sheet.png');
  await page.screenshot({path:output,fullPage:true});
  console.log(output);
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
