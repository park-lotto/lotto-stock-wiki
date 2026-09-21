// 채널명 칸 슬라이더 전수 검사 — 2026-09-21 사장님 "체널칸 상단제목칸도 조절하는게 이상해".
//   템플릿마다 훅·본문에서 슬라이더를 움직이고, **채널 글자·캡슐·바탕그림이 같은 양**만큼
//   움직이는지 잰다. 하나라도 따로 놀면 화면에서 글자가 캡슐 밖으로 떨어져 나온다.
//   실행: node tools/qa_channel_slot_all.js [url]
const puppeteer=require('puppeteer');
const url=process.argv[2]||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const TOL=0.8;   // 허용 어긋남(%) — 글자 높이 반올림 정도는 눈에 안 띈다

(async()=>{
  const browser=await puppeteer.launch({headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1600,height:1100});
  await page.setCacheEnabled(false);
  const errors=[];page.on('pageerror',e=>errors.push(String(e).slice(0,140)));
  await page.goto(url,{waitUntil:'networkidle0'});
  await new Promise(r=>setTimeout(r,900));

  const snap=()=>page.evaluate(()=>{
    const pv=document.querySelector('#a-live-preview').getBoundingClientRect();
    const pct=v=>(v-pv.top)/pv.height*100;
    const one=sel=>{const e=document.querySelector(sel);if(!e)return null;const r=e.getBoundingClientRect();return r.height<1?null:pct(r.top)};
    const base=document.querySelector('.precision-base');
    const 그림=base&&base.getBoundingClientRect().height>1?pct(base.getBoundingClientRect().top):null;
    return {글자:one('.precision-text[data-edit-bind="channel"]'),
            캡슐:one('.precision-patch[data-edit-bind="channel"]'),
            그림:그림};
  });

  const fails=[];const rows=[];
  for(const mode of ['story','continuous']){
    await page.evaluate(m=>document.querySelector(`[data-template-mode="${m}"]`)?.click(),mode);
    await new Promise(r=>setTimeout(r,450));
    const n=await page.$$eval('[data-p20]',e=>e.length);
    for(let i=0;i<n;i++){
      await page.evaluate(i=>document.querySelector(`[data-p20="${i}"]`)?.click(),i);
      await new Promise(r=>setTimeout(r,330));
      for(const scene of (mode==='story'?[0,1]:[0])){
        await page.evaluate(s=>document.querySelector(`[data-scene-step="${s===0?-1:1}"]`)?.click(),scene);
        await new Promise(r=>setTimeout(r,330));
        await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
        const name=await page.evaluate(()=>document.querySelector('[data-stage-name]')?.textContent?.trim().slice(0,10)||'');
        const where=`${mode}/${name}/${scene?'본문':'훅'}`;
        const input=await page.$('[data-fixed-range="channel"]');
        if(!input){rows.push({어디:where,상태:'슬라이더 없음'});continue;}
        const start=await snap();
        // 기본값에서 +6% 올려본다
        const base0=await page.evaluate(()=>Number(document.querySelector('[data-fixed-range="channel"]').value)||0);
        await page.evaluate(v=>{const i=document.querySelector('[data-fixed-range="channel"]');i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));},base0+6);
        await new Promise(r=>setTimeout(r,450));
        const moved=await snap();
        const d=k=>(start[k]==null||moved[k]==null)?null:+(moved[k]-start[k]).toFixed(2);
        const 글자=d('글자'),캡슐=d('캡슐'),그림=d('그림');
        const 있는것=[['글자',글자],['캡슐',캡슐],['그림',그림]].filter(([,v])=>v!=null);
        rows.push({어디:where,글자,캡슐,그림});
        if(글자==null){fails.push(`${where} → 채널 글자가 없다`);continue;}
        for(const [nm,v] of 있는것){
          if(nm==='글자')continue;
          if(Math.abs(v-글자)>TOL)fails.push(`${where} → 글자 ${글자}% vs ${nm} ${v}% (${Math.abs(v-글자).toFixed(2)}% 어긋남)`);
        }
        if(Math.abs(글자)<0.3)fails.push(`${where} → 슬라이더를 올려도 채널명이 안 움직인다`);
        // 되돌린다
        await page.evaluate(v=>{const i=document.querySelector('[data-fixed-range="channel"]');i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));},base0);
        await new Promise(r=>setTimeout(r,250));
      }
    }
  }
  const 캡슐있는것=rows.filter(r=>r.캡슐!=null).length;
  console.log(JSON.stringify({검사한칸:rows.length,캡슐있는템플릿:캡슐있는것,실패:fails.length,
    실패목록:fails.slice(0,25),페이지오류:[...new Set(errors)]},null,1));
  console.log(fails.length===0&&errors.length===0?'전부 통과':`실패 ${fails.length}건`);
  await browser.close();
  process.exit(fails.length===0&&errors.length===0?0:1);
})().catch(e=>{console.error(e);process.exit(1)});
