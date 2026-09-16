const puppeteer=require('puppeteer');
(async()=>{
 const b=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:'new'});
 const p=await b.newPage();
 await p.setViewport({width:900,height:1500,deviceScaleFactor:1.5});
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
 await p.evaluate(()=>{const c=[...document.querySelectorAll('.preset-card')].find(x=>/이븐쇼핑/.test(x.textContent));if(c)c.click();});
 await new Promise(r=>setTimeout(r,300));
 // 채널 입력칸 찾기
 const ch=await p.evaluate(()=>{
   const all=[...document.querySelectorAll('input,textarea')].map((i,ix)=>({ix,val:i.value,type:i.type}));
   return all.filter(x=>x.type==='text'||x.type===''||!x.type).slice(0,12);
 });
 console.log('INPUTS', JSON.stringify(ch));
 // 이미지 교체 시도 후 실제 src 확인
 const r=await p.evaluate(()=>{
   const el=document.querySelector('#a-live-preview');
   const before=[...el.querySelectorAll('img')].map(i=>i.className+'|'+i.src.slice(-40));
   el.querySelectorAll('.precision-media,.scene-lens').forEach(n=>{n.src='/out/assets/scene-style/cms/07.jpg';});
   const mid=[...el.querySelectorAll('img')].map(i=>i.className+'|'+i.src.slice(-40));
   window.sceneStyle.refresh();
   const after=[...el.querySelectorAll('img')].map(i=>i.className+'|'+i.src.slice(-40));
   return {before,mid,after};
 });
 console.log('IMG', JSON.stringify(r,null,1));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
