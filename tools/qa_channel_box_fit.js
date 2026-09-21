// 채널명 글자가 **캡슐(channel_box) 안에** 있는가 — 2026-09-21 사장님 "체널명 크기 조정이나 제목 들어가는 곳이 깨진다".
//   ★DOM 셀렉터로 캡슐을 찾지 않는다. 오늘 그렇게 했다가 60칸 중 5칸만 재고 "통과"를 냈다.
//     캡슐 좌표는 템플릿 데이터(channel_box)에 있다 — 그걸 화면 비율로 환산해 글자와 대조한다.
//   실행: node tools/qa_channel_box_fit.js [url]
const puppeteer=require('puppeteer');
const url=process.argv[2]||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const TOL=2;   // px 여유(미리보기 기준). 1080px 실화면에선 약 3배로 보인다.

(async()=>{
  const browser=await puppeteer.launch({headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1600,height:1100});
  await page.setCacheEnabled(false);
  const errors=[];page.on('pageerror',e=>errors.push(String(e).slice(0,140)));
  await page.goto(url,{waitUntil:'networkidle0'});
  await new Promise(r=>setTimeout(r,900));

  const measure=()=>page.evaluate(()=>{
    const api=window.sceneStyle, snap=api?.snapshot?.();
    if(!snap)return null;
    const rows=(window.PRECISION20||[]).concat(window.CONTINUOUS20||[]);
    const preset=rows.find(r=>r.id===snap.presetId);
    if(!preset)return null;
    const frame=preset.frame||(snap.frameKind==='body'?preset.body:preset.hook);
    const box=frame?.channel_box||(frame?.channel_boxes||[])[0];
    if(!box)return {박스없음:true};
    // ★캡슐은 두 종류다(2026-09-21에 갈랐다):
    //   designed:true  = 캡슐이 **배경 그림**에 이미 그려져 있다 → 데이터 좌표가 진짜 기준.
    //   그 외          = 캡슐을 DOM으로 그리고 **글자 폭에 맞춰 늘린다** → 데이터 좌표와 달라도 정상.
    //                    이 경우는 실제로 그려진 상자(DOM)와 글자를 대조해야 한다.
    const drawn=document.querySelector('.precision-patch[data-edit-bind="channel"]');
    const pv=document.querySelector('#a-live-preview').getBoundingClientRect();
    const sx=pv.width/frame.width, sy=pv.height/frame.height;
    const el=document.querySelector('.precision-text[data-edit-bind="channel"]');
    if(!el||el.hidden)return {글자없음:true};
    const rg=document.createRange();rg.selectNodeContents(el);const t=rg.getBoundingClientRect();
    if(t.height<1)return {글자없음:true};
    let 기준;
    if(box.designed||!drawn){
      기준={좌:pv.left+box.x*sx,우:pv.left+(box.x+box.width)*sx,
            위:pv.top+box.y*sy,아래:pv.top+(box.y+box.height)*sy};
    }else{
      const d=drawn.getBoundingClientRect();
      기준={좌:d.left,우:d.right,위:d.top,아래:d.bottom};
    }
    return {종류:(box.designed?'그림캡슐':(drawn?'DOM캡슐':'상자없음')),
      박스:기준, 글자:{좌:t.left,우:t.right,위:t.top,아래:t.bottom},
      글꼴:getComputedStyle(el).fontSize};
  });
  const judge=m=>{
    if(!m||m.박스없음||m.글자없음)return null;
    return {좌:Math.round(m.박스.좌-m.글자.좌),우:Math.round(m.글자.우-m.박스.우),
            위:Math.round(m.박스.위-m.글자.위),아래:Math.round(m.글자.아래-m.박스.아래),
            글꼴:m.글꼴,종류:m.종류};
  };
  const fails=[];let 잰칸=0;
  for(const mode of ['story','continuous']){
    await page.evaluate(m=>document.querySelector(`[data-template-mode="${m}"]`)?.click(),mode);
    await new Promise(r=>setTimeout(r,450));
    const n=await page.$$eval('[data-p20]',e=>e.length);
    for(let i=0;i<n;i++){
      await page.evaluate(i=>document.querySelector(`[data-p20="${i}"]`)?.click(),i);
      await new Promise(r=>setTimeout(r,320));
      for(const sc of (mode==='story'?[0,1]:[0])){
        await page.evaluate(s=>document.querySelector(`[data-scene-step="${s===0?-1:1}"]`)?.click(),sc);
        await new Promise(r=>setTimeout(r,320));
        await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
        const name=await page.evaluate(()=>document.querySelector('[data-stage-name]')?.textContent?.trim().slice(0,10)||'');
        const where=`${mode}/${name}/${sc?'본문':'훅'}`;
        const base=judge(await measure());
        if(!base)continue;
        잰칸++;
        const report=(tag,j)=>{ if(!j)return;
          for(const [k,label] of [['좌','왼쪽'],['우','오른쪽'],['위','위'],['아래','아래']])
            if(j[k]>TOL)fails.push(`${where}[${j.종류}] ${tag} → 채널명이 상자 ${label}으로 ${j[k]}px 넘침(글꼴 ${j.글꼴})`);
        };
        report('기본',base);
        await page.evaluate(()=>{const f=document.querySelector('[data-field-key="channel"]');
          const b=f?.querySelector('[data-font-step="0.1"]');if(b)for(let i=0;i<5;i++)b.click();});
        await new Promise(r=>setTimeout(r,600));
        report('키운뒤',judge(await measure()));
        await page.evaluate(()=>{const f=document.querySelector('[data-field-key="channel"]');
          const b=f?.querySelector('[data-font-step="-0.1"]');if(b)for(let i=0;i<5;i++)b.click();});
        await new Promise(r=>setTimeout(r,400));
      }
    }
  }
  const unique=[...new Set(fails)];
  console.log(JSON.stringify({잰칸,실패:unique.length,실패목록:unique.slice(0,25),페이지오류:[...new Set(errors)]},null,1));
  await browser.close();
  process.exit(unique.length===0&&errors.length===0?0:1);
})().catch(e=>{console.error(e);process.exit(1)});
