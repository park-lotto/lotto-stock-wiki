const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const ids=['s0034','s0035','s0090','s0093','s0121','s0144','s0145','s0155','s0195','s0217','s0218','s0234','s0241','s0291','s0311','s0340','s0430','s0431','s0446','s0460'];

(async()=>{
  const browser=await puppeteer.launch({headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1100,height:1420,deviceScaleFactor:1});
  const cards=ids.map((id,index)=>{
    const file=path.join(process.env.TEMP,`cleanup-${String(index).padStart(2,'0')}-${id}.png`);
    const image=`data:image/png;base64,${fs.readFileSync(file).toString('base64')}`;
    return `<div class="card"><img src="${image}"><b>${index+1} · ${id}</b></div>`;
  }).join('');
  await page.setContent(`<style>body{margin:0;padding:20px;background:#07131d;color:white;font:14px sans-serif}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}.card{display:grid;gap:5px;text-align:center}.card img{width:180px;height:320px;object-fit:contain;background:#000;border:1px solid #35505b}</style><div class="grid">${cards}</div>`,{waitUntil:'networkidle0'});
  const output=path.join(process.env.TEMP,'fixed20-contact-sheet.png');
  await page.screenshot({path:output,fullPage:true});
  console.log(output);
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
