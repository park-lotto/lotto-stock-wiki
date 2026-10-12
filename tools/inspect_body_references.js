const fs=require('fs'),path=require('path'),puppeteer=require('puppeteer');
(async()=>{
 const browser=await puppeteer.launch({headless:true});const page=await browser.newPage();
 await page.setViewport({width:1500,height:900});
 await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
 const rows=await page.evaluate(()=>window.PRECISION20.map(p=>({id:p.id,name:p.name,image:p.body_image})));
 await page.setContent(`<body style="margin:0;background:#19212c;color:white;display:grid;grid-template-columns:repeat(5,1fr);gap:12px;font:14px sans-serif">${rows.map(p=>`<div><p>${p.id} ${p.name}</p><img style="width:100%" src="http://127.0.0.1:8767/out/${p.image}"></div>`).join('')}</body>`);
 await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode())));
 await page.screenshot({path:path.join(process.env.TEMP,'body-originals.png'),fullPage:true});
 await browser.close();
})();
