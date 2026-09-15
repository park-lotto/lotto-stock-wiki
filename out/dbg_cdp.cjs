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
 const cdp=await p.target().createCDPSession();
 const state=async(tag)=>{const s=await p.evaluate(()=>{const el=window.__card;const n=el.querySelector('.precision-text.center');
   return {tf:getComputedStyle(n).transform,img:el.querySelector('.precision-media').src.slice(-12),anims:document.getAnimations().length};});
   console.log(tag,JSON.stringify(s));};
 await p.evaluate(()=>{const el=window.__card;
   el.querySelectorAll('.precision-media,.scene-lens').forEach(n=>n.src='/out/assets/scene-style/cms/07.jpg');
   window.sceneStyle.motionAt(0);});
 await state('BEFORE');
 const r=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,
    clip:{x:0,y:0,width:304,height:540,scale:1.5}});
 require('fs').writeFileSync('out/_cdp0.png',Buffer.from(r.data,'base64'));
 await state('AFTER ');
 // 두 번째 시점도
 await p.evaluate(()=>{const el=window.__card;
   el.querySelectorAll('.precision-media,.scene-lens').forEach(n=>n.src='/out/assets/scene-style/cms/07.jpg');
   window.sceneStyle.motionAt(120);});
 const r2=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,
    clip:{x:0,y:0,width:304,height:540,scale:1.5}});
 require('fs').writeFileSync('out/_cdp120.png',Buffer.from(r2.data,'base64'));
 await state('AFTER2');
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
