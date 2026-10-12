const puppeteer=require('puppeteer');
const H1='최민식이 기억하는',H2='80년대 출연료',BT='최민식 첫 출연료 150만원의 진실',CH='디씨썰극장';
(async()=>{
 const b=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:'new'});
 const p=await b.newPage(); await p.setViewport({width:900,height:1500,deviceScaleFactor:1.5});
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
 await p.evaluate(()=>{const c=[...document.querySelectorAll('.preset-card')].find(x=>/이븐쇼핑/.test(x.textContent));if(c)c.click();
   const pop=document.querySelector('[data-hook-motion="pop"]'); if(pop)pop.click();});
 await new Promise(r=>setTimeout(r,400));
 await p.evaluate((h1,h2,bt,ch)=>{window.__H1=h1;window.__H2=h2;window.__BT=bt;window.__CH=ch;},H1,H2,BT,CH);
 await p.evaluate(()=>{const el=document.querySelector('#a-live-preview');
   const r=el.getBoundingClientRect();const w=Math.round(r.width),h=Math.round(r.height);
   document.body.appendChild(el);
   [...document.body.children].forEach(n=>{if(n!==el)n.style.display='none';});
   document.body.style.cssText='margin:0;padding:0;background:#0b0b0b';
   Object.assign(el.style,{position:'absolute',left:'0',top:'0',margin:'0',width:w+'px',height:h+'px'});
   window.sceneStyle.refresh(); window.__card=el;});
 await new Promise(r=>setTimeout(r,200));
 // 훅 단계 그대로 재현
 const st=await p.evaluate(()=>{
   const el=window.__card; window.sceneStyle.show(0);
   const ins=[...document.querySelectorAll('input,textarea')];
   const put=(ix,v)=>{const e=ins[ix];if(!e||v==null)return;e.value=v;
     e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));};
   put(7,window.__CH);put(8,window.__H1);put(9,window.__H2);put(10,window.__BT);
   const R=el.getBoundingClientRect();
   return [...el.querySelectorAll('.precision-text')].map(n=>{const bb=n.getBoundingClientRect();
     return {txt:(n.textContent||'').slice(0,20),top:Math.round(bb.top-R.top),op:getComputedStyle(n).opacity};});
 });
 console.log('show(0)+put 직후:', JSON.stringify(st));
 const st2=await p.evaluate(()=>{
   const el=window.__card;
   document.getAnimations().forEach(a=>{try{a.cancel();}catch(e){}});
   window.sceneStyle.motionAt(574);
   const R=el.getBoundingClientRect();
   return [...el.querySelectorAll('.precision-text')].map(n=>{const bb=n.getBoundingClientRect();
     return {txt:(n.textContent||'').slice(0,20),top:Math.round(bb.top-R.top),op:getComputedStyle(n).opacity};});
 });
 console.log('motionAt(574) 후 :', JSON.stringify(st2));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
