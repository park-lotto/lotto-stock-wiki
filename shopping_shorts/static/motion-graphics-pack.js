// 🎞 모션그래픽팩(관제 222, 2026-10-17 사장님 "모션그래픽팩으로 · 이런 영상의 모션그래픽을 고급으로 · 창작하지 말고 찾아서 써라").
// ★효과는 레퍼런스 영상을 실측해서 그대로 옮긴 것만 둔다 — 크기·색·두께·시간표는 전부 재서 얻은 숫자다(지어낸 값 없음).
//   효과마다 src(레퍼런스 주소·잰 구간)를 남긴다. 새 효과 = 영상을 받아 재고 → 아래 ITEMS 에 한 칸.
// ★판단 주인: 효과의 모양·시간표·장면 안 자리(place)는 이 파일 하나다.
//   편집기 미리보기·완성본 렌더·썸네일은 scene-decoration-catalog.js paint/animate 가 여기 poster/clock 을 부르고,
//   렌더러는 sceneDecorations.motionAt → tick() 으로 프레임마다 다시 그린다.
//   캡컷은 이 효과가 든 장면을 완성본에서 그대로 떠 온다(scene_style._needs_bake) — 정지 그림으로 멈추지 않게.
(()=>{
const base=((document.currentScript&&document.currentScript.src)||'').replace(/[^/]*$/,'');
const FONT='MGRighteous';
// Righteous(OFL, Google Fonts) — 레퍼런스 숫자와 글꼴 59개(우리)+47개(구글) 겹침 대조 1위(0.79, 우리 글꼴 최고 0.62). licenses/Righteous-OFL.txt
try{const face=new FontFace(FONT,`url("${base}fonts/Righteous-Regular.ttf")`);document.fonts.add(face);face.load().catch(()=>{});}catch(e){}

// ── ① 3·2·1 원형 카운트다운 ─────────────────────────────────────────────
// src: youtube.com/shorts/xbyBPW8jIKw (@살림장착) 1.20~3.35초, 1080×1920 프레임 실측(2026-10-17).
//   좌표는 효과 상자(484px 정사각, 1080 화면 기준) 안 — 원 중심 (242,242).
//   흰 원: 반지름 202·두께 30(r 187~217) / 진행 막대: 같은 두께·끝 둥글게, 12시부터 시계 방향,
//   색 = 선형 그라데이션 #ADFD7D→#FFFD15 (중심에서 ±(180,70.5), 원 위 85점 회귀 오차 R5·G4·B11) / 막대 끝 점: 지름 83·#38F8EC·궤도 반지름 200
//   숫자: 흰색 높이 184·중심 (247,242)·오른쪽으로 0.15 기울임(3·2 = Righteous, 1 = 실측 막대) / 그림자 없음(원 바깥 밝기 차 0)
//   시간표: 0초 3(바로 다 나옴) → 0.750초 2 → 1.567초 1. 바뀔 때 새 숫자가 절반 크기로 0.067초 → 원래 크기.
//   진행 각도 = 아래 실측표(30fps 프레임 번호, 각도) — 레퍼런스는 15fps 계단이라 점 사이를 잇는다.
//   1.967초 뒤는 실측 곡선의 대칭(한 바퀴 3.04초, 가속·감속 대칭 — 맞춤 오차 8°)으로 채운다.
//   레퍼런스는 2.15초에 다음 장면으로 넘어가며 사라진다 → 장면 끝에 맞춰 끝나게 놓는다(place).
const CD_ANGLE=[[0,0],[2,.2],[4,.5],[6,1.3],[8,2.4],[10,3.9],[12,5.8],[14,8.1],[15,11],[17,14.4],[19,18.5],[21,23.1],[23,28.5],[25,34.7],[27,41.9],[29,50.1],[30,59.4],[32,70],[34,81.8],[36,95.1],[38,109.9],[40,126.2],[42,143.6],[44,162.1],[45,180.9],[47,199.6],[49,217.7],[51,234.5],[53,250.2],[55,264.3],[57,277.2],[59,287.8]];
const CD_TURN=3040,CD_LAST=CD_ANGLE[CD_ANGLE.length-1];
function table(ms){
  const f=ms/1000*30;if(f<=0)return 0;
  for(let i=1;i<CD_ANGLE.length;i++){const [f1,a1]=CD_ANGLE[i];if(f<=f1){const [f0,a0]=CD_ANGLE[i-1];return a0+(a1-a0)*(f-f0)/(f1-f0);}}
  return CD_LAST[1];
}
function cdAngle(ms){
  const lastMs=CD_LAST[0]/30*1000;
  if(ms<=lastMs)return table(ms);
  const mirror=t=>360-table(CD_TURN-t),m0=mirror(lastMs);
  return Math.min(360,CD_LAST[1]+(mirror(Math.min(ms,CD_TURN))-m0)*(360-CD_LAST[1])/(360-m0));
}
const cdHeight={};
function cdDraw(ctx,S,ms){
  const k=S/484;ctx.save();ctx.scale(k,k);
  const C=242,R=202,a=cdAngle(ms),top=-Math.PI/2;
  ctx.lineWidth=30;ctx.strokeStyle='#FFFFFF';ctx.beginPath();ctx.arc(C,C,R,0,Math.PI*2);ctx.stroke();
  if(a>0){
    const g=ctx.createLinearGradient(C-180,C-70.5,C+180,C+70.5);g.addColorStop(0,'#ADFD7D');g.addColorStop(1,'#FFFD15');
    ctx.strokeStyle=g;ctx.lineCap='round';ctx.beginPath();ctx.arc(C,C,R,top,top+a*Math.PI/180);ctx.stroke();
  }
  const rad=(a-90)*Math.PI/180;ctx.fillStyle='#38F8EC';ctx.beginPath();ctx.arc(C+200*Math.cos(rad),C+200*Math.sin(rad),41.5,0,Math.PI*2);ctx.fill();
  const digit=ms<750?'3':ms<1567?'2':'1',pop=(ms>=750&&ms<817)||(ms>=1567&&ms<1633)?.5:1;
  if(digit==='1'){
    // 레퍼런스의 1 은 깃발 없는 막대다(Righteous 1 에는 깃발이 있다) — 실측 꼭짓점 그대로: 폭 36 · 위 (248~283,146) · 아래 (217~252,339) · 중심 (250,242.5)
    ctx.translate(250,242.5);ctx.scale(pop,pop);ctx.fillStyle='#FFFFFF';ctx.beginPath();
    ctx.moveTo(-2,-96.5);ctx.lineTo(33,-96.5);ctx.lineTo(2,96.5);ctx.lineTo(-33,96.5);ctx.closePath();ctx.fill();ctx.restore();return;
  }
  // 글꼴 크기 = 그 숫자의 잉크 높이가 184 가 되게(글꼴 지표로 잰다 — 숫자마다 높이가 조금 다르다)
  const key=digit+(document.fonts.check(`100px ${FONT}`)?'1':'0');
  if(!cdHeight[key]){ctx.font=`100px ${FONT}, sans-serif`;const t=ctx.measureText(digit);cdHeight[key]=(t.actualBoundingBoxAscent+t.actualBoundingBoxDescent)||70;}
  const size=184/cdHeight[key]*100*pop;ctx.font=`${size}px ${FONT}, sans-serif`;
  const t=ctx.measureText(digit),w=t.actualBoundingBoxLeft+t.actualBoundingBoxRight,h=t.actualBoundingBoxAscent+t.actualBoundingBoxDescent;
  ctx.translate(247,242);ctx.transform(1,0,-.15,1,0,0);ctx.fillStyle='#FFFFFF';
  ctx.fillText(digit,-w/2+t.actualBoundingBoxLeft,h/2-t.actualBoundingBoxDescent);
  ctx.restore();
}

const ITEMS={
  countdown321:{label:'3·2·1 카운트다운',moment:'제품 공개 직전·결과 보여주기 직전 (장면 끝에 맞춰 끝남)',
    src:{url:'https://youtube.com/shorts/xbyBPW8jIKw',span:'1.20~3.35초'},
    duration:2150,poster:300,box:{l:27.6,t:42.7,w:44.8},draw:cdDraw},
};

// 장면 안 자리: 장면 끝에 맞춰 끝난다(레퍼런스 = 다음 장면으로 넘어가며 사라짐). 장면이 효과보다 짧으면 시간표를 줄여 장면에 맞춘다.
function place(item,sceneMs){
  const d=item.duration;if(!(sceneMs>0))return {delay:0,span:d};
  return {delay:Math.max(0,sceneMs-d),span:Math.min(d,sceneMs)};
}
function paintAt(canvas,id,ms){
  const item=ITEMS[id];if(!item)return;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
  if(ms===null||ms<0||ms>item.duration)return;item.draw(ctx,canvas.width,ms);
}
// 효과의 시계 = 빈 Web Animation. 렌더러가 motionAt 으로 currentTime 을 박으면 그 순간의 그림을 그린다(다른 꾸밈 움직임과 같은 길).
//   편집 화면에서는 효과를 되풀이해 보여 주고(0.7초 쉼), 내보낼 때(window.sceneStyleExporting)는 장면 안 자리(place)대로 한 번만.
const GAP=700;
function localMs(el){
  const anim=el.getAnimations().find(a=>a.id==='mograph');if(!anim)return undefined;
  const item=ITEMS[el.dataset.mograph];if(!item)return undefined;
  const c=anim.effect.getComputedTiming();if(c.progress===null)return null;
  return anim.effect.getTiming().iterations===Infinity?c.progress*(item.duration+GAP):c.progress*item.duration;
}
function drawEl(el){const canvas=el.querySelector('canvas');if(!canvas)return;const ms=localMs(el);if(ms===undefined)return;paintAt(canvas,el.dataset.mograph,ms);}
function tick(root){(root||document).querySelectorAll('[data-mograph]').forEach(drawEl);}
(function loop(){try{tick();}catch(e){}requestAnimationFrame(loop);})();

window.MOTION_GRAPHICS={
  items:ITEMS,place,paintAt,tick,
  // 정지 그림 자세(렌더러가 장면 정지 그림을 찍기 직전) — 대표 시각(poster)으로 세운다
  still(root){(root||document).querySelectorAll('[data-mograph-still]').forEach(el=>{const a=el.getAnimations().find(x=>x.id==='mograph');if(a){a.pause();a.currentTime=Number(el.dataset.mographStill);drawEl(el);}});},
  // 항목 하나를 그릴 캔버스(scene-decoration-catalog.js paint). 시계가 붙기 전 정지 그림 = poster 시각.
  poster(el,m,W){
    const item=ITEMS[m.mograph];if(!item)return;
    const canvas=document.createElement('canvas'),px=Math.max(64,Math.round(W*m.w/100*Math.min(2,window.devicePixelRatio||1)));
    canvas.width=canvas.height=px;canvas.style.width='100%';canvas.style.height='100%';canvas.style.display='block';
    el.dataset.mograph=m.mograph;el.style.background='transparent';el.style.borderRadius='0';el.append(canvas);paintAt(canvas,m.mograph,item.poster);
  },
  // 시계 붙이기(scene-decoration-catalog.js animate). sceneMs = 그 장면 길이.
  clock(el,m,sceneMs){
    const item=ITEMS[m.mograph];if(!item)return;
    const anim=window.sceneStyleExporting
      ?(()=>{const p=place(item,sceneMs),a=el.animate([],{duration:p.span,delay:p.delay,fill:'none',iterations:1});
          // 내보낼 때 첫 정지 그림(썸네일·캡컷 예비)은 poster 시각으로 고정 — 실제 흐른 시간에 따라 그림이 달라지지 않게. 프레임은 motionAt 이 박는다.
          el.dataset.mographStill=String(p.delay+item.poster*p.span/item.duration);a.pause();a.currentTime=Number(el.dataset.mographStill);return a;})()
      :el.animate([],{duration:item.duration+GAP,iterations:Infinity});
    anim.id='mograph';drawEl(el);
  },
  // 새 항목 기본값(놓는 자리 = 레퍼런스 자리, 정사각)
  defaults(id){const item=ITEMS[id];if(!item)return null;const b=item.box;return {kind:'mograph',mograph:id,l:b.l,t:b.t,w:b.w,h:b.w*9/16,shape:'rect',fx:'solid',color:'#FFFFFF',op:100,soft:0,rot:0,motion:'none'};},
};
})();
