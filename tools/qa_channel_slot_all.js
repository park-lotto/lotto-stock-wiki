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
    const media=document.querySelector('.precision-media');
    const mr=media?media.getBoundingClientRect():null;
    return {글자:one('.precision-text[data-edit-bind="channel"]'),
            // ★캡슐·돋보기는 data-edit-bind가 없다 — frame.surfaces에서 온 .body-material 패치다.
            //   2026-09-21: 종전 셀렉터(data-edit-bind="channel")는 엉뚱한 걸 재서 통과시켰다.
            캡슐:(()=>{
              // 머리띠 '바탕'(맨 위를 덮는 넓은 면)은 움직이면 안 되니 세지 않는다 —
              // 실제 캡슐은 둥근 모서리가 있는 조각이다(2026-09-21 실측으로 갈랐다).
              // ★'머리띠 안'에 있는 것만 캡슐로 본다 — 제목 아래 서브카피 띠(둥근 모서리)를
              //   캡슐로 잘못 잡아 16건을 거짓 실패로 냈다(2026-09-21 실측으로 갈랐다).
              const chEl=document.querySelector('.precision-text[data-edit-bind="channel"]');
              const chBottom=chEl?pct(chEl.getBoundingClientRect().bottom):8;
              const els=[...document.querySelectorAll('.precision-patch.body-material,.scene-brand-ink')]
                .filter(e=>{const r=e.getBoundingClientRect();
                  if(r.height<3)return false;
                  if(pct(r.top)>chBottom+1)return false;   // 머리띠 아래 것은 채널명과 무관하다
                  return parseFloat(getComputedStyle(e).borderRadius)>1;});
              if(!els.length)return null;
              return Math.min(...els.map(e=>pct(e.getBoundingClientRect().top)));})(),
            그림:그림,
            // ★영상이 미리보기 아래까지 채우는가 — 2026-09-21 회귀(영상만 위로 올라가 아래가 검정).
            영상아래:mr?+pct(mr.bottom).toFixed(1):null};
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
        // 영상이 화면 아래(100%)까지 안 닿으면 그만큼 검정 빈칸이 남는다
        if(moved.영상아래!=null&&moved.영상아래<99)fails.push(`${where} → 영상 아래가 ${moved.영상아래}%에서 끊긴다(검정 빈칸 ${(100-moved.영상아래).toFixed(1)}%)`);
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
