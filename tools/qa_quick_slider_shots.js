// '빠른 조절' 슬라이더(채널명 칸·상단 제목칸)를 끝에서 끝까지 움직이며 미리보기 상단을 캡처한다.
//   2026-09-21 사장님이 짚은 곳 — 글자 ＋/−가 아니라 이 슬라이더다. 먼저 눈으로 본다(숫자 검사는 그 다음).
//   실행: node tools/qa_quick_slider_shots.js <출력폴더> [url] / PRESETS="이븐쇼핑,활용정점." (없으면 전부) / NAME=채널명
const puppeteer=require('puppeteer'),fs=require('fs');
const out=process.argv[2]||'.tmp/slider-shots',url=process.argv[3]||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const only=(process.env.PRESETS||'').split(',').map(s=>s.trim()).filter(Boolean),NAME=process.env.NAME||'';
fs.mkdirSync(out,{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const browser=await puppeteer.launch({headless:true});const page=await browser.newPage();
  await page.setViewport({width:1600,height:1100,deviceScaleFactor:2});await page.setCacheEnabled(false);
  const errors=[];page.on('pageerror',e=>errors.push(String(e).slice(0,140)));
  await page.goto(url,{waitUntil:'networkidle0'});await wait(900);
  const setRange=async(key,v)=>{await page.evaluate((key,v)=>{const r=document.querySelector('[data-fixed-range="'+key+'"]');if(!r)return;
    r.value=String(v);r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));},key,v);await wait(700);};
  const info=()=>page.evaluate(()=>{const g=k=>{const r=document.querySelector('[data-fixed-range="'+k+'"]');return r?{v:Number(r.value),min:Number(r.min),max:Number(r.max),숨김:!r.offsetParent}:null};return {channel:g('channel'),top:g('top')}});
  const shoot=async name=>{const c=await page.evaluate(()=>{const r=document.querySelector('#a-live-preview').getBoundingClientRect();return {x:r.left,y:r.top,width:r.width,height:r.height*.62}});
    await page.screenshot({path:out+'/'+name+'.png',clip:c});};
  let no=0;const log=[];
  for(const mode of ['story','continuous']){
    await page.evaluate(m=>{const e=document.querySelector('[data-template-mode="'+m+'"]');if(e)e.click();},mode);await wait(450);
    const n=await page.$$eval('[data-p20]',e=>e.length);
    for(let i=0;i<n;i++){
      await page.evaluate(i=>{const e=document.querySelector('[data-p20="'+i+'"]');if(e)e.click();},i);await wait(320);
      const name=await page.evaluate(()=>{const e=document.querySelector('[data-stage-name]');return e?e.textContent.trim().slice(0,10):''});
      if(only.length&&!only.some(o=>name.startsWith(o)))continue;
      for(const sc of (mode==='story'?[0,1]:[0])){
        await page.evaluate(s=>{const e=document.querySelector('[data-scene-step="'+(s===0?-1:1)+'"]');if(e)e.click();},sc);await wait(400);
        await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
        if(NAME)await page.evaluate(v=>{const f=document.querySelector('[data-field-key="channel"]');const i=f&&f.querySelector('input,textarea');if(i){i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));}},NAME);
        await wait(1200);
        const base=await info();if(!base.channel)continue;
        const tag=String(++no).padStart(2,'0')+'_'+name.replace(/[\/\\.\s]+/g,'_')+'_'+(sc?'본문':'훅');
        await shoot(tag+'_0처음(채널'+base.channel.v+'_상단'+base.top.v+')');
        for(const v of [base.channel.min,Math.round((base.channel.min+base.channel.max)/2),base.channel.max]){await setRange('channel',v);await wait(900);await shoot(tag+'_1채널칸'+String(v).padStart(2,'0'));}
        await setRange('channel',base.channel.v);await wait(900);await shoot(tag+'_2채널칸원복');
        for(const v of [base.top.min,Math.round((base.top.min+base.top.max)/2),base.top.max]){await setRange('top',v);await wait(900);await shoot(tag+'_3상단칸'+String(v).padStart(2,'0'));}
        await setRange('top',base.top.v);await wait(900);await shoot(tag+'_4상단칸원복');
        log.push({칸:tag,처음:base});
      }
    }
  }
  console.log(JSON.stringify({캡처칸:log.length,log,페이지오류:[...new Set(errors)]},null,0));
  await browser.close();
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
