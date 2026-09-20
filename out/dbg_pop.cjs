const puppeteer=require('puppeteer');
(async()=>{
 const b=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:'new'});
 const p=await b.newPage(); await p.setViewport({width:900,height:1500,deviceScaleFactor:1.5});
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
 await p.evaluate(()=>{const c=[...document.querySelectorAll('.preset-card')].find(x=>/이븐쇼핑/.test(x.textContent));if(c)c.click();
   const pop=document.querySelector('[data-hook-motion="pop"]'); if(pop)pop.click();});
 await new Promise(r=>setTimeout(r,400));
 await p.evaluate(()=>{const el=document.querySelector('#a-live-preview');
   const r=el.getBoundingClientRect(); const w=Math.round(r.width),h=Math.round(r.height);
   document.body.appendChild(el);
   [...document.body.children].forEach(n=>{if(n!==el)n.style.display='none';});
   document.body.style.cssText='margin:0;padding:0;background:#0b0b0b';
   Object.assign(el.style,{position:'absolute',left:'0',top:'0',margin:'0',width:w+'px',height:h+'px'});
   window.sceneStyle.refresh(); window.__card=el;});
 await new Promise(r=>setTimeout(r,200));
 // 사진 넣고 시간별 transform 확인
 const out=await p.evaluate(()=>{
   const el=window.__card;
   el.querySelectorAll('.precision-media,.scene-lens').forEach(n=>n.src='/out/assets/scene-style/cms/07.jpg');
   return [0,60,120,250,374].map(ms=>{ window.sceneStyle.motionAt(ms);
     const n=el.querySelector('.precision-text.center');
     return {ms, tf:getComputedStyle(n).transform, op:getComputedStyle(n).opacity,
             img:el.querySelector('.precision-media').src.slice(-12)};});
 });
 console.log(JSON.stringify(out,null,1));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
