const puppeteer=require('puppeteer');
(async()=>{
 const b=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:'new'});
 const p=await b.newPage(); await p.setViewport({width:900,height:1500,deviceScaleFactor:1.5});
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
 await p.evaluate(()=>{const c=[...document.querySelectorAll('.preset-card')].find(x=>/이븐쇼핑/.test(x.textContent));if(c)c.click();});
 await new Promise(r=>setTimeout(r,400));
 const info=await p.evaluate(()=>{
  const el=document.querySelector('#a-live-preview');
  el.querySelectorAll('.precision-media,.scene-lens').forEach(n=>n.src='/out/assets/scene-style/cms/07.jpg');
  const layers=[...el.querySelectorAll('*')].filter(n=>{
    const s=getComputedStyle(n); return s.backgroundImage&&s.backgroundImage!=='none';
  }).map(n=>({cls:(n.className||'').toString().slice(0,34), bg:s2(n)}));
  function s2(n){return getComputedStyle(n).backgroundImage.slice(0,70)}
  const imgs=[...el.querySelectorAll('img')].map(i=>({cls:i.className,src:i.src.slice(-34),
     w:Math.round(i.getBoundingClientRect().width),h:Math.round(i.getBoundingClientRect().height),
     op:getComputedStyle(i).opacity, z:getComputedStyle(i).zIndex, disp:getComputedStyle(i).display}));
  return {layers, imgs, cardBg:getComputedStyle(el).backgroundImage.slice(0,80)};
 });
 console.log(JSON.stringify(info,null,1));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
