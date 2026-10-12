const puppeteer=require('puppeteer');
(async()=>{
 const b=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:'new'});
 const p=await b.newPage();
 await p.setViewport({width:900,height:1500,deviceScaleFactor:1.5});
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
 const before=await p.evaluate(()=>{const e=document.querySelector('#a-live-preview');const r=e.getBoundingClientRect();
   return {w:r.width,h:r.height,disp:getComputedStyle(e).display,vis:getComputedStyle(e).visibility,
           parent:e.parentElement.className.slice(0,40), pdisp:getComputedStyle(e.parentElement).display};});
 console.log('BEFORE', JSON.stringify(before));
 await p.evaluate(()=>{const c=[...document.querySelectorAll('.preset-card')].find(x=>/이븐쇼핑/.test(x.textContent)); if(c)c.click();});
 await new Promise(r=>setTimeout(r,300));
 const after=await p.evaluate(()=>{const e=document.querySelector('#a-live-preview');const r=e.getBoundingClientRect();
   return {w:r.width,h:r.height,cls:e.className};});
 console.log('AFTER CLICK', JSON.stringify(after));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
