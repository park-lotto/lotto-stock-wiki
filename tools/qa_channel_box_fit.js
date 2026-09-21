// 채널명이 **눈에 보이는 것** 안에 있는가 — 2026-09-21 사장님 "체널명 크기 조정이나 제목 들어가는 곳이 깨진다".
//   ★기준은 데이터 좌표(channel_box)가 아니다. 그 상자는 60칸 중 55칸에서 화면에 안 보인다 →
//     그걸로 재면 "124건"처럼 눈엔 멀쩡한 헛경보가 쏟아진다(09-21 실측, 캡처 240장으로 확인).
//   보는 것 3가지(전부 실제로 그려진 DOM):
//     ① 보이는 캡슐(.precision-patch 중 둥근 모서리·테두리·바탕과 다른 색) → 글자 잉크가 그 안
//     ② 캡슐이 없으면 머리띠(글자 중심을 품은 넓은 패치) → 글자가 위아래로 그 안, 좌우는 화면 안
//     ③ 아이콘(.body-ornament) → 글자와 안 겹침
//   세로는 폰트 줄 상자가 아니라 **글자 잉크**(canvas measureText)로 잰다 — 줄 상자는 폰트마다 1.2~1.5배라 헛경보가 난다.
//   실행: node tools/qa_channel_box_fit.js [url]
//         SHOT=폴더 → 칸마다 원본/덧그림 캡처(빨강=기준, 파랑=글자 잉크, 주황=아이콘) / STEPS=＋ 누르는 횟수(기본 5)
const puppeteer=require('puppeteer');
const fs=require('fs');
const url=process.argv[2]||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const SHOT=process.env.SHOT||'';if(SHOT)fs.mkdirSync(SHOT,{recursive:true});
const STEPS=Number(process.env.STEPS||5);
const TOL=1.5;   // px(미리보기 기준). 1080px 실화면에선 약 3배.

const measureInPage=()=>{
  const pv=document.querySelector('#a-live-preview');if(!pv)return null;
  const el=pv.querySelector('.precision-text[data-edit-bind="channel"]');
  if(!el||el.hidden)return {채널없음:true};
  const rg=document.createRange();rg.selectNodeContents(el);const line=rg.getBoundingClientRect();
  if(line.height<1||line.width<1)return {채널없음:true};
  const cs=getComputedStyle(el),ctx=document.createElement('canvas').getContext('2d');
  ctx.font=cs.fontStyle+' '+cs.fontWeight+' '+cs.fontSize+' '+cs.fontFamily;
  const m=ctx.measureText(el.textContent||'');
  const fb=(m.fontBoundingBoxAscent+m.fontBoundingBoxDescent)||line.height;
  const baseline=line.top+m.fontBoundingBoxAscent*(line.height/fb);
  const ink={좌:line.left,우:line.right,위:baseline-m.actualBoundingBoxAscent,아래:baseline+m.actualBoundingBoxDescent};
  const cx=(ink.좌+ink.우)/2,cy=(ink.위+ink.아래)/2,P=pv.getBoundingClientRect();
  const rectOf=e=>{const r=e.getBoundingClientRect();return {좌:r.left,우:r.right,위:r.top,아래:r.bottom,w:r.width,h:r.height}};
  const holds=[...pv.querySelectorAll('.precision-patch')].map(e=>({r:rectOf(e),s:getComputedStyle(e)}))
    .filter(x=>x.r.w>3&&x.r.h>3&&x.r.좌<=cx&&x.r.우>=cx&&x.r.위<=cy&&x.r.아래>=cy).sort((a,b)=>a.r.w*a.r.h-b.r.w*b.r.h);
  const opaque=c=>c&&c!=='transparent'&&!/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)/.test(c);
  const visible=(x,i)=>{
    if(x.r.w>=P.width*.8)return false;                                   // 화면 폭을 거의 다 덮으면 캡슐이 아니라 띠다
    if(parseFloat(x.s.borderTopLeftRadius)>0||parseFloat(x.s.borderTopWidth)>0)return true;
    if(x.s.backgroundImage&&x.s.backgroundImage!=='none')return true;
    return false;   // 그 밖(바탕과 같은 색 상자 등)은 DOM만으론 보이는지 알 수 없다 → 아래 픽셀 검사가 잡는다
  };
  const capsule=holds.find(visible);
  const band=holds.find(x=>x.r.w>=P.width*.8);
  const icons=[...pv.querySelectorAll('.body-ornament')].map(rectOf).filter(r=>r.w>2&&r.아래>ink.위&&r.위<ink.아래);
  const screen={좌:P.left,우:P.right,위:P.top,아래:P.bottom};
  return {글꼴:cs.fontSize,ink,화면:screen,기준종류:capsule?'캡슐':(band?'머리띠':'화면'),기준:capsule?capsule.r:(band?band.r:screen),icons};
};
const judge=m=>{
  if(!m||m.채널없음)return null;const out=[],k=m.ink,b=m.기준;
  const over=(v,label)=>{if(v>TOL)out.push(m.기준종류+' '+label+'으로 '+Math.round(v)+'px 넘침')};
  if(m.기준종류==='캡슐'){over(b.좌-k.좌,'왼쪽');over(k.우-b.우,'오른쪽');}
  else{over(m.화면.좌-k.좌,'화면 왼쪽');over(k.우-m.화면.우,'화면 오른쪽');}
  if(m.기준종류==='캡슐'){over(b.위-k.위,'위');over(k.아래-b.아래,'아래');}else{over(m.화면.위-k.위,'화면 위');}
  (m.색경계||[]).forEach(t=>out.push(t));
  m.icons.forEach(r=>{const ov=Math.min(k.우,r.우)-Math.max(k.좌,r.좌);if(ov>-2)out.push('아이콘과 '+(ov>0?Math.round(ov)+'px 겹침':'붙음'))});
  return out;
};

(async()=>{
  const browser=await puppeteer.launch({headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1600,height:1100,deviceScaleFactor:SHOT?3:1});
  await page.setCacheEnabled(false);
  const errors=[];page.on('pageerror',e=>errors.push(String(e).slice(0,140)));
  await page.goto(url,{waitUntil:'networkidle0'});
  await new Promise(r=>setTimeout(r,900));
  let shotNo=0;
  const shoot=async(where,tag,m)=>{
    if(!SHOT||!m||!m.ink)return;
    const top=Math.max(0,Math.min(m.기준.위,m.ink.위,m.화면.위)-10),bottom=Math.max(m.기준.아래,m.ink.아래)+25;
    const clip={x:m.화면.좌,y:top,width:m.화면.우-m.화면.좌,height:Math.min(1100-top,Math.max(20,bottom-top))};
    if(!(clip.width>0&&clip.height>0))return;
    const name=String(++shotNo).padStart(3,'0')+'_'+where.replace(/[\/\\.\s]+/g,'_')+'_'+tag;
    try{await page.screenshot({path:SHOT+'/'+name+'_raw.png',clip});}catch(e){return;}
    await page.evaluate(list=>{for(const [r,c] of list){const d=document.createElement('div');d.className='__qa_ov';
      Object.assign(d.style,{position:'fixed',left:r.좌+'px',top:r.위+'px',width:(r.우-r.좌)+'px',height:(r.아래-r.위)+'px',outline:'1px solid '+c,zIndex:99999,pointerEvents:'none'});document.body.append(d);}},
      [[m.기준,'red'],[m.ink,'blue'],...m.icons.map(r=>[r,'orange'])]);
    await page.screenshot({path:SHOT+'/'+name+'_box.png',clip});
    await page.evaluate(()=>document.querySelectorAll('.__qa_ov').forEach(e=>e.remove()));
  };
  const press=async(step,count)=>{
    await page.evaluate((step,count)=>{const f=document.querySelector('[data-field-key="channel"]');
      const b=f&&f.querySelector('[data-font-step="'+step+'"]');if(b)for(let i=0;i<count;i++)b.click();},step,count);
    await new Promise(r=>setTimeout(r,500));
  };
  // ★훅에는 모션(줌 펀치 등)이 있다 — 누른 직후에 재면 글자가 이동 중이라 헛값이 나온다(09-21 덧그림으로 확인).
  //   연속 두 번 잰 값이 같아질 때까지 기다린다(최대 4초). 끝까지 안 멈추면 '안멈춤'으로 표시한다.
  const stable=async()=>{
    let prev=null;
    for(let i=0;i<20;i++){
      const m=await page.evaluate(measureInPage);
      if(!m||m.채널없음)return m;
      if(prev&&['좌','우','위','아래'].every(k=>Math.abs(m.ink[k]-prev.ink[k])<.3&&Math.abs(m.기준[k]-prev.기준[k])<.3))return m;
      prev=m;await new Promise(r=>setTimeout(r,200));
    }
    prev.안멈춤=true;return prev;
  };
  // ★픽셀 검사 — 글자 잉크 바로 바깥 네 방향의 바탕색이 서로 같아야 한다. 다르면 글자가 **눈에 보이는 경계**(띠 끝·알약 끝)에 걸친 것이다.
  //   DOM 상자로는 '보이는지'를 알 수 없어서(바탕과 같은 색 캡슐 20칸이 헛경보를 냈다) 화면 그대로를 본다.
  const DPR=SHOT?3:1,GAP=3,DIFF=70;
  // hidden: 이 칸의 캡슐이 안 보인다고 기본 상태에서 이미 정했으면(true) 다시 묻지 않는다 — 키운 글자가 표본점에 걸려 판정이 뒤집힌다.
  const colorEdges=async(m,hidden)=>{
    if(!m||!m.ink)return;
    if(hidden&&m.기준종류==='캡슐'){m.기준종류='머리띠';m.기준=m.화면;}
    if(m.기준종류==='캡슐'){   // 둥근 모서리가 있어도 바탕과 같은 색이면 눈엔 안 보인다(고정형 20칸: 검정 띠 위 검정 캡슐)
      const c=m.기준,q=4,clip={x:Math.max(0,c.좌-q),y:Math.max(0,c.위-q),width:(c.우-c.좌)+q*2,height:(c.아래-c.위)+q*2};
      const b64=await page.screenshot({clip,encoding:'base64'});
      const seen=await page.evaluate(async(b64,w,h,q,dpr)=>{
        const img=new Image();img.src='data:image/png;base64,'+b64;await img.decode();
        const cv=document.createElement('canvas');cv.width=img.width;cv.height=img.height;const x=cv.getContext('2d');x.drawImage(img,0,0);
        const at=(px,py)=>{const d=x.getImageData(Math.min(img.width-1,Math.max(0,Math.round(px*dpr))),Math.min(img.height-1,Math.max(0,Math.round(py*dpr))),1,1).data;return [d[0],d[1],d[2]]};
        const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
        // 가장자리 네 곳(글자가 닿기 어려운 모서리 쪽)에서 안쪽 3px ↔ 바깥 3px
        const pts=[[q+w*.12,q,0,1],[q+w*.88,q,0,1],[q+w*.12,q+h,0,-1],[q+w*.88,q+h,0,-1],[q,q+h*.5,1,0],[q+w,q+h*.5,-1,0]];
        return Math.max(...pts.map(([px,py,dx,dy])=>dist(at(px+dx*3,py+dy*3),at(px-dx*3,py-dy*3))));
      },b64,c.우-c.좌,c.아래-c.위,q,DPR);
      m.캡슐대비=Math.round(seen);
      if(seen<25){m.기준종류='머리띠';m.기준=m.화면;m.캡슐숨음=true;}   // 안 보이는 캡슐은 기준이 못 된다
    }
    const k=m.ink,pad=GAP+3,clip={x:Math.max(0,k.좌-pad),y:Math.max(0,k.위-pad),width:(k.우-k.좌)+pad*2,height:(k.아래-k.위)+pad*2};
    const b64=await page.screenshot({clip,encoding:'base64'});
    const cols=await page.evaluate(async(b64,w,h,pad,gap,dpr)=>{
      const img=new Image();img.src='data:image/png;base64,'+b64;await img.decode();
      const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const x=c.getContext('2d');x.drawImage(img,0,0);
      const avg=(cx,cy,rw,rh)=>{const d=x.getImageData(Math.max(0,Math.round((cx-rw/2)*dpr)),Math.max(0,Math.round((cy-rh/2)*dpr)),Math.max(1,Math.round(rw*dpr)),Math.max(1,Math.round(rh*dpr))).data;
        let r=0,g=0,b=0,n=d.length/4;for(let i=0;i<d.length;i+=4){r+=d[i];g+=d[i+1];b+=d[i+2];}return [r/n,g/n,b/n];};
      const W=w+pad*2,H=h+pad*2,o=pad-gap;   // 잉크에서 gap만큼 떨어진 얇은 띠
      return {위:avg(W/2,o,w*.6,1.5),아래:avg(W/2,H-o,w*.6,1.5),왼쪽:avg(o,H/2,1.5,h*.5),오른쪽:avg(W-o,H/2,1.5,h*.5)};
    },b64,k.우-k.좌,k.아래-k.위,pad,GAP,DPR);
    const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]),keys=Object.keys(cols);
    m.색경계=keys.filter(s=>keys.filter(t=>t!==s&&dist(cols[s],cols[t])>DIFF).length>=2)   // 나머지 셋 중 둘 이상과 색이 다르면 그쪽이 경계 밖
      .map(s=>'글자 '+s+'이 다른 색 면에 걸침(보이는 경계 넘음)');
  };
  const NAME=process.env.NAME||'';   // 채널명을 바꿔 넣고 잰다(긴 이름 시험)
  const typeName=async()=>{
    if(!NAME)return;
    await page.evaluate(v=>{const f=document.querySelector('[data-field-key="channel"]');const i=f&&f.querySelector('input,textarea');
      if(i){i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}));}},NAME);
    await new Promise(r=>setTimeout(r,300));
  };
  const fails=[];let 잰칸=0;const 기준집계={};
  for(const mode of ['story','continuous']){
    await page.evaluate(m=>{const e=document.querySelector('[data-template-mode="'+m+'"]');if(e)e.click();},mode);
    await new Promise(r=>setTimeout(r,450));
    const n=await page.$$eval('[data-p20]',e=>e.length);
    for(let i=0;i<n;i++){
      await page.evaluate(i=>{const e=document.querySelector('[data-p20="'+i+'"]');if(e)e.click();},i);
      await new Promise(r=>setTimeout(r,320));
      for(const sc of (mode==='story'?[0,1]:[0])){
        await page.evaluate(s=>{const e=document.querySelector('[data-scene-step="'+(s===0?-1:1)+'"]');if(e)e.click();},sc);
        await new Promise(r=>setTimeout(r,320));
        await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
        const name=await page.evaluate(()=>{const e=document.querySelector('[data-stage-name]');return e?e.textContent.trim().slice(0,10):''});
        const where=mode+'/'+name+'/'+(sc?'본문':'훅');
        await typeName();const m0=await stable();await colorEdges(m0);const j0=judge(m0);
        if(!j0)continue;
        잰칸++;기준집계[m0.기준종류]=(기준집계[m0.기준종류]||0)+1;
        if(m0.안멈춤)fails.push(where+' → 화면이 4초 안에 안 멈춘다(측정 불신)');
        j0.forEach(t=>fails.push(where+' 기본('+m0.글꼴+') → '+t));await shoot(where,'기본',m0);
        await press('0.1',STEPS);
        const m1=await stable();await colorEdges(m1,!!m0.캡슐숨음);(judge(m1)||[]).forEach(t=>fails.push(where+' 키운뒤('+m1.글꼴+') → '+t));await shoot(where,'키운뒤',m1);
        // 원복: 한계에 닿으면 ＋가 더 안 먹으므로 '누른 만큼 −'가 아니라 **표시가 100%가 될 때까지** −를 누른다(사장님이 하는 방식)
        for(let t=0;t<30;t++){
          const pct=await page.evaluate(()=>{const o=document.querySelector('[data-field-key="channel"] .font-stepper output');return o?parseInt(o.textContent,10):100});
          if(pct<=100)break;await press('-0.1',1);
        }
        const m2=await stable();if(m2&&m0.캡슐숨음&&m2.기준종류==='캡슐'){m2.기준종류='머리띠';m2.기준=m2.화면;}   // 원복: 키웠다 줄이면 처음 자리로 돌아와야 한다(v186·v187이 여기서 미완이었다)
        if(m2&&m2.ink&&['좌','우','위','아래'].some(k=>Math.abs(m2.ink[k]-m0.ink[k])>1||Math.abs(m2.기준[k]-m0.기준[k])>1))fails.push(where+' 원복 → 키웠다 줄였더니 처음 자리와 다르다');
      }
    }
  }
  const unique=[...new Set(fails)];
  console.log(JSON.stringify({잰칸,기준집계,실패:unique.length,실패목록:unique,페이지오류:[...new Set(errors)]},null,1));
  await browser.close();
  process.exit(unique.length===0&&errors.length===0?0:1);
})().catch(e=>{console.error(e);process.exit(1)});
