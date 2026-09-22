// '채널명 칸' 슬라이더 전수 검사(썰쇼핑형 훅·본문 40칸) — 사장님 기준(2026-09-21): **칸의 높이만** 바뀐다.
//   검사: ①글자 크기 불변 ②늘어난 만큼 제목·자막칸·영상이 같은 양으로 밀린다 ③같은 줄 아이콘이 채널명과 같이 움직인다
//         ④채널명이 제목과 안 겹친다 ⑤처음 값으로 되돌리면 제자리
//   기준 상태 = 슬라이더를 처음 값으로 한 번 '건드린' 상태(훅 제목이 첫 조작에 29.65→32.65px로 바뀌는 v182 기존 결함을 이 검사에서 떼어 놓기 위해).
//   실행: node tools/qa_channel_block_all.js [url]    SHOT=폴더 → 칸마다 최대값 화면 캡처
//   ★이 검사는 옛 코드(v182)에서 실패해야 정상이다 — 먼저 그걸 확인하고 믿을 것.
const puppeteer=require('puppeteer'),fs=require('fs');
const url=process.argv[2]||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html',SHOT=process.env.SHOT||'';if(SHOT)fs.mkdirSync(SHOT,{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const browser=await puppeteer.launch({headless:true});const page=await browser.newPage();
  await page.setViewport({width:1600,height:1100,deviceScaleFactor:SHOT?2:1});await page.setCacheEnabled(false);
  const errors=[];page.on('pageerror',e=>errors.push(String(e).slice(0,140)));
  await page.goto(url,{waitUntil:'networkidle0'});await wait(900);
  const read=()=>page.evaluate(()=>{
    const pv=document.querySelector('#a-live-preview'),P=pv.getBoundingClientRect(),pos=e=>{const r=e.getBoundingClientRect();return {top:(r.top-P.top)/P.height*100,bottom:(r.bottom-P.top)/P.height*100}};
    const ink=e=>{const g=document.createRange();g.selectNodeContents(e);const r=g.getBoundingClientRect();return {top:(r.top-P.top)/P.height*100,bottom:(r.bottom-P.top)/P.height*100}};
    const out={texts:{},icons:[]};
    ['channel','hook1','hook2','bodyTitle','caption'].forEach(b=>{const e=pv.querySelector('.precision-text[data-edit-bind="'+b+'"]');if(e&&!e.hidden&&e.getBoundingClientRect().height>1)out.texts[b]={...pos(e),ink:ink(e),font:parseFloat(getComputedStyle(e).fontSize)};});
    const ch=out.texts.channel;
    pv.querySelectorAll('.body-ornament').forEach(e=>{const p=pos(e);if(ch&&p.top<ch.bottom&&p.bottom>ch.top)out.icons.push(p);});
    const m=pv.querySelector('.scene-media-clip'),cm=pv.querySelector('.caption-mask');out.media=m?pos(m).top:null;out.captionBand=cm?pos(cm).top:null;
    const r=document.querySelector('[data-fixed-range="channel"]');out.slider=r?Number(r.value):null;out.sliderHidden=r?!r.offsetParent:true;
    return out;});
  const setRange=async v=>{await page.evaluate(v=>{const r=document.querySelector('[data-fixed-range="channel"]');r.value=String(v);r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));},v);
    let prev='';for(let i=0;i<12;i++){await wait(250);const cur=JSON.stringify(await read());if(cur===prev)break;prev=cur;}};
  const near=(a,b,t)=>Math.abs(a-b)<=t,f=v=>Math.round(v*10)/10;
  const fails=[];let cells=0;
  await page.evaluate(()=>{const e=document.querySelector('[data-template-mode="story"]');if(e)e.click();});await wait(450);
  const n=await page.$$eval('[data-p20]',e=>e.length);
  for(let i=0;i<n;i++){
    await page.evaluate(i=>document.querySelector('[data-p20="'+i+'"]').click(),i);await wait(320);
    const name=await page.evaluate(()=>document.querySelector('[data-stage-name]').textContent.trim().slice(0,10));
    for(const sc of [0,1]){
      await page.evaluate(s=>document.querySelector('[data-scene-step="'+(s===0?-1:1)+'"]').click(),sc);await wait(1600);
      await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
      const where=name+'/'+(sc?'본문':'훅'),first=await read();
      if(first.slider==null||!first.texts.channel)continue;
      cells++;const base=first.slider,bad=t=>fails.push(where+' → '+t);
      await setRange(base);const A=await read();
      const steps=[[Math.min(20,base+5),'＋5'],[20,'최대']];
      for(const [v,label] of steps){
        await setRange(v);const S=await read(),want=v-base,d=S.media!=null&&A.media!=null?S.media-A.media:null;
        for(const b of Object.keys(A.texts))if(S.texts[b]&&!near(S.texts[b].font,A.texts[b].font,.05))bad(label+': '+b+' 글자 크기가 바뀐다 '+f(A.texts[b].font)+'→'+f(S.texts[b].font)+'px');
        if(d==null||!near(d,want,.4))bad(label+': 영상 시작이 칸이 늘어난 만큼('+want+'%) 안 밀린다 — 실제 '+(d==null?'없음':f(d))+'%');
        for(const b of ['hook1','hook2','bodyTitle'])if(A.texts[b]&&S.texts[b]&&!near(S.texts[b].top-A.texts[b].top,want,.6))bad(label+': '+b+' 가 '+want+'% 가 아니라 '+f(S.texts[b].top-A.texts[b].top)+'% 움직였다');
        if(A.captionBand!=null&&S.captionBand!=null&&!near(S.captionBand-A.captionBand,want,.4))bad(label+': 자막칸이 '+f(S.captionBand-A.captionBand)+'% 움직였다(기대 '+want+')');
        const chMove=S.texts.channel.top-A.texts.channel.top;
        if(!near(chMove,want/2,.5))bad(label+': 채널명이 칸 가운데를 안 따라간다 — '+f(chMove)+'% (기대 '+f(want/2)+')');
        A.icons.forEach((ic,k)=>{const s=S.icons[k];if(!s||!near(s.top-ic.top,chMove,.4))bad(label+': 아이콘'+(k+1)+'이 채널명과 따로 논다 — 아이콘 '+(s?f(s.top-ic.top):'사라짐')+'% / 채널명 '+f(chMove)+'%');});
        const firstTitle=['hook1','hook2','bodyTitle'].map(b=>S.texts[b]).filter(Boolean).sort((a,b)=>a.ink.top-b.ink.top)[0];
        if(firstTitle&&S.texts.channel.ink.bottom>firstTitle.ink.top+.3)bad(label+': 채널명이 제목과 겹친다 — 채널명 끝 '+f(S.texts.channel.ink.bottom)+'% > 제목 시작 '+f(firstTitle.ink.top)+'%');
        if(SHOT&&label==='최대'){const c=await page.evaluate(()=>{const r=document.querySelector('#a-live-preview').getBoundingClientRect();return {x:r.left,y:Math.max(0,r.top),width:r.width,height:r.height*.62}});
          await page.screenshot({path:SHOT+'/'+String(cells).padStart(2,'0')+'_'+where.replace(/[\/\\.\s]+/g,'_')+'_최대.png',clip:c});}
      }
      await setRange(base);const D=await read();
      for(const b of Object.keys(A.texts))if(!D.texts[b]||!near(D.texts[b].top,A.texts[b].top,.25)||!near(D.texts[b].font,A.texts[b].font,.05))bad('원복: '+b+' 가 제자리로 안 온다');
      if(A.media!=null&&!near(D.media,A.media,.25))bad('원복: 영상 시작이 제자리로 안 온다');
      A.icons.forEach((ic,k)=>{if(!D.icons[k]||!near(D.icons[k].top,ic.top,.25))bad('원복: 아이콘'+(k+1)+'이 제자리로 안 온다');});
    }
  }
  const unique=[...new Set(fails)],byCell={};unique.forEach(t=>{const k=t.split(' → ')[0];(byCell[k]=byCell[k]||[]).push(t.split(' → ')[1]);});
  console.log(JSON.stringify({잰칸:cells,실패칸:Object.keys(byCell).length,실패건:unique.length,페이지오류:[...new Set(errors)]}));
  Object.entries(byCell).forEach(([k,v])=>console.log('  '+k.padEnd(20)+' | '+v.slice(0,4).join(' / ').slice(0,210)+(v.length>4?' …(+'+(v.length-4)+')':'')));
  await browser.close();process.exit(unique.length===0&&errors.length===0?0:1);
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
