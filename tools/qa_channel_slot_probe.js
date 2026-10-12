// '채널명 칸' 슬라이더를 직접 움직여, 머리띠 부품(띠·글자·알약·아이콘·구분선·제목·영상)이 각각 어떻게 변하는지 적는다.
//   사장님 기준(2026-09-21): **칸의 높이만** 바뀐다. 글자 크기는 그대로, 부품은 칸 안에 같이 있는다.
//   실행: node tools/qa_channel_slot_probe.js [PRESET이름] [본문|훅] [값,값,...]   예) node tools/qa_channel_slot_probe.js 이븐쇼핑 본문 7,12,20
const puppeteer=require('puppeteer');
const want=process.argv[2]||'이븐쇼핑',kind=process.argv[3]||'본문',values=(process.argv[4]||'').split(',').filter(Boolean).map(Number);
const url=process.env.URL||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const b=await puppeteer.launch({headless:true});const p=await b.newPage();await p.setViewport({width:1600,height:1100});await p.setCacheEnabled(false);
  const errs=[];p.on('pageerror',e=>errs.push(String(e).slice(0,140)));
  await p.goto(url,{waitUntil:'networkidle0'});await wait(900);
  const n=await p.$$eval('[data-p20]',e=>e.length);let found=false;
  for(let i=0;i<n&&!found;i++){await p.evaluate(i=>document.querySelector('[data-p20="'+i+'"]').click(),i);await wait(300);
    found=(await p.evaluate(()=>document.querySelector('[data-stage-name]').textContent.trim())).startsWith(want);}
  if(!found){console.log('프리셋 없음');await b.close();return;}
  await p.evaluate(s=>document.querySelector('[data-scene-step="'+(s?1:-1)+'"]').click(),kind==='본문');await wait(1500);
  const snap=()=>p.evaluate(()=>{
    const pv=document.querySelector('#a-live-preview'),P=pv.getBoundingClientRect(),pct=v=>Math.round((v-P.top)/P.height*1000)/10;
    const row=(e,label)=>{const r=e.getBoundingClientRect();return {무엇:label,위:pct(r.top),아래:pct(r.bottom),높이:Math.round(r.height/P.height*1000)/10,글꼴:e.classList.contains('precision-text')?getComputedStyle(e).fontSize:undefined}};
    const out=[];
    pv.querySelectorAll('.precision-patch').forEach(e=>{const r=e.getBoundingClientRect();if(r.top-P.top<P.height*.45&&r.height>0.4)out.push(row(e,'면'+(e.classList.contains('body-material')?'(surface)':'')+(e.dataset.editBind?'['+e.dataset.editBind+']':'')+' w'+Math.round(r.width/P.width*100)+'%'+(parseFloat(getComputedStyle(e).borderTopLeftRadius)>0?' 둥근':'')));});
    pv.querySelectorAll('.body-ornament').forEach(e=>out.push(row(e,'아이콘 '+e.className.replace('body-ornament body-ornament-',''))));
    pv.querySelectorAll('.precision-text').forEach(e=>{if(!e.hidden&&['channel','hook1','hook2','bodyTitle','caption'].includes(e.dataset.editBind))out.push(row(e,'글자['+e.dataset.editBind+']'));});
    const media=pv.querySelector('.precision-media');if(media)out.push(row(media,'영상'));
    const r=document.querySelector('[data-fixed-range="channel"]');
    return {슬라이더:r?Number(r.value):null,rows:out};});
  const setRange=async v=>{await p.evaluate(v=>{const r=document.querySelector('[data-fixed-range="channel"]');r.value=String(v);r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));},v);await wait(1200);};
  const first=await snap();const list=values.length?values:[first.슬라이더,Math.min(20,first.슬라이더+6),20,first.슬라이더];
  const table={};
  for(const v of list){await setRange(v);const s=await snap();s.rows.forEach(r=>{(table[r.무엇]=table[r.무엇]||[]).push(`${r.위}~${r.아래}${r.글꼴?'('+Math.round(parseFloat(r.글꼴)*10)/10+'px)':''}`)});}
  console.log('프리셋',want,kind,'| 채널명 칸 값 →',list.join(' → '),'| 단위: 화면 높이 대비 % (위~아래)');
  Object.entries(table).forEach(([k,v])=>console.log('  '+k.padEnd(34),v.join('  →  ')));
  console.log('페이지오류',errs);await b.close();
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
