window.SCENE_DECORATION_CATALOG={
  emoji:[
    ['시선',['🔥','✨','💥','⚡','🚨','❗','❓','👀','📌','🎯','💯','🆕']],
    ['감정',['😍','🤩','😱','🥹','😳','🤔','😮','🥰','👍','👏','🙌','🫶']],
    ['쇼핑',['🛒','🎁','💰','💸','🏷️','✅','⭐','💎','🧾','📦','🚚','🔖']],
    ['살림',['🏠','🧹','🧼','🍳','🧴','🧺','☕','🌿','🐾','🛁','🪥','🧊']]
  ],
  badges:['SALE','NEW','인기','추천','필수','1위','할인','품절임박','재구매','강추']
};

(()=>{
function _shapeGrad(ctx, color, r){
  // 단색보다 살짝 밝은 → 진한 그라데이션이 입체감을 만든다(플랫 단색은 싸구려로 보인다).
  const g = ctx.createLinearGradient(0, -r, 0, r);
  g.addColorStop(0, _lighten(color, 28));
  g.addColorStop(1, color);
  return g;
}

function _lighten(hex, amt){
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '#FF3B30'));
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  const c = i => Math.min(255, ((n >> i) & 255) + amt);
  return `rgb(${c(16)},${c(8)},${c(0)})`;
}

const THUMB_SHAPES = {
  // 곡선 화살표 — 손으로 그린 듯 휘어지며 끝이 뾰족해지는 형태(붓 느낌).
  // 왼쪽에서 출발해 위로 휜 뒤 오른쪽 아래를 가리키는 곡선 화살표.
  // ★몸통을 stroke로 긋고 촉을 그 **끝점의 접선 방향**에 맞춰 붙인다. 처음엔 몸통(채움)과 촉을
  //   따로 좌표로 찍었는데 촉이 몸통에서 떨어져 엉뚱한 곳을 가리켰다(실측) — 곡선 끝과 촉을
  //   손으로 맞추면 반드시 어긋난다. 끝점·각도를 하나의 값에서 뽑아 쓴다.
  arrow_curve(ctx, r, color){
    const grad = _shapeGrad(ctx, color, r);
    // 곡선: (-0.72,0.18) → 제어점 (-0.15,-0.62) → 끝 (0.42,-0.02)
    const p0 = [-0.72 * r, 0.18 * r], cp = [-0.15 * r, -0.62 * r], p1 = [0.42 * r, -0.02 * r];
    ctx.strokeStyle = grad;
    ctx.lineWidth = r * 0.23; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(p0[0], p0[1]);
    ctx.quadraticCurveTo(cp[0], cp[1], p1[0], p1[1]);
    ctx.stroke();
    // 촉 방향 = 끝점에서의 접선(2차 베지어는 끝점 접선이 제어점→끝점 방향).
    const ang = Math.atan2(p1[1] - cp[1], p1[0] - cp[0]);
    ctx.save();
    ctx.translate(p1[0], p1[1]); ctx.rotate(ang);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(0.30 * r, 0);                       // 뾰족한 끝
    ctx.lineTo(-0.16 * r, -0.28 * r);
    ctx.lineTo(-0.16 * r, 0.28 * r);
    ctx.closePath(); ctx.fill();
    ctx.restore();
  },
  // 굵은 직선 화살표 — 둥근 끝단이라 딱딱하지 않다
  arrow_bold(ctx, r, color){
    ctx.strokeStyle = _shapeGrad(ctx, color, r);
    ctx.lineWidth = r * 0.30; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath(); ctx.moveTo(-0.55 * r, 0); ctx.lineTo(0.18 * r, 0); ctx.stroke();
    ctx.fillStyle = _shapeGrad(ctx, color, r);
    ctx.beginPath();
    ctx.moveTo(0.62 * r, 0); ctx.lineTo(0.10 * r, -0.38 * r); ctx.lineTo(0.10 * r, 0.38 * r);
    ctx.closePath(); ctx.fill();
  },
  // 원을 도는 화살표 — '여기 주목' 표시로 흔히 쓰는 그 모양
  arrow_circle(ctx, r, color){
    ctx.strokeStyle = _shapeGrad(ctx, color, r);
    ctx.lineWidth = r * 0.22; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.arc(0, 0, r * 0.52, Math.PI * 0.75, Math.PI * 1.95); ctx.stroke();
    ctx.fillStyle = _shapeGrad(ctx, color, r);
    ctx.save(); ctx.translate(r * 0.50, r * -0.18); ctx.rotate(Math.PI * 0.28);
    ctx.beginPath(); ctx.moveTo(0.28 * r, 0); ctx.lineTo(-0.10 * r, -0.24 * r);
    ctx.lineTo(-0.10 * r, 0.24 * r); ctx.closePath(); ctx.fill(); ctx.restore();
  },
  // 말풍선 — 안에 글자 레이어를 얹어 쓰라고 비워둔다
  bubble(ctx, r, color){
    ctx.fillStyle = _shapeGrad(ctx, color, r);
    const w = r * 1.15, h = r * 0.78, rad = r * 0.26;
    ctx.beginPath();
    ctx.moveTo(-w + rad, -h);
    ctx.arcTo(w, -h, w, h, rad); ctx.arcTo(w, h, -w, h, rad);
    ctx.arcTo(-w, h, -w, -h, rad); ctx.arcTo(-w, -h, w, -h, rad);
    ctx.closePath(); ctx.fill();
    ctx.beginPath();                                  // 꼬리
    ctx.moveTo(-r * 0.28, h * 0.92); ctx.lineTo(-r * 0.10, h * 1.55);
    ctx.lineTo(r * 0.16, h * 0.92); ctx.closePath(); ctx.fill();
  },
  // 폭발(번쩍) — 별 모양 톱니. 가격·혜택 강조에 쓴다
  burst(ctx, r, color){
    ctx.fillStyle = _shapeGrad(ctx, color, r);
    ctx.beginPath();
    const n = 12;
    for (let i = 0; i < n * 2; i++){
      const rad = i % 2 ? r * 0.56 : r * 0.98;
      const a = (Math.PI * i) / n - Math.PI / 2;
      const fn = i ? 'lineTo' : 'moveTo';
      ctx[fn](Math.cos(a) * rad, Math.sin(a) * rad);
    }
    ctx.closePath(); ctx.fill();
  },
  // 동그라미 테두리 — 제품·부위를 감싸 '여기를 보라'
  circle_ring(ctx, r, color){
    ctx.strokeStyle = _shapeGrad(ctx, color, r);
    ctx.lineWidth = r * 0.17; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.ellipse(0, 0, r * 0.86, r * 0.66, -0.12, 0.25, Math.PI * 2.05);
    ctx.stroke();
  },
  // 체크 — 손글씨 느낌의 굵은 획
  check(ctx, r, color){
    ctx.strokeStyle = _shapeGrad(ctx, color, r);
    ctx.lineWidth = r * 0.26; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(-0.62 * r, 0.02 * r); ctx.lineTo(-0.16 * r, 0.46 * r); ctx.lineTo(0.64 * r, -0.48 * r);
    ctx.stroke();
  },
  // 엑스 — 비교·부정 표시
  cross(ctx, r, color){
    ctx.strokeStyle = _shapeGrad(ctx, color, r);
    ctx.lineWidth = r * 0.26; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(-0.5 * r, -0.5 * r); ctx.lineTo(0.5 * r, 0.5 * r);
    ctx.moveTo(0.5 * r, -0.5 * r); ctx.lineTo(-0.5 * r, 0.5 * r);
    ctx.stroke();
  },
  // 밑줄 강조 획 — 글자 아래 따로 얹어 쓰는 굵은 붓선
  swoosh(ctx, r, color){
    ctx.strokeStyle = _shapeGrad(ctx, color, r);
    ctx.lineWidth = r * 0.20; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(-0.92 * r, 0.18 * r);
    ctx.quadraticCurveTo(0, -0.30 * r, 0.92 * r, 0.10 * r);
    ctx.stroke();
  },
};

// 도형 목록(UI 순서) — 라벨은 사장님이 고를 때 보는 이름이다.
const THUMB_SHAPE_LIST = [
  {key: 'arrow_curve',  label: '곡선 화살표', color: '#FF3B30'},
  {key: 'arrow_bold',   label: '굵은 화살표', color: '#FF3B30'},
  {key: 'arrow_circle', label: '도는 화살표', color: '#FFD400'},
  {key: 'swoosh',       label: '강조 획',     color: '#FFD400'},
  {key: 'circle_ring',  label: '동그라미',    color: '#FF3B30'},
  {key: 'burst',        label: '번쩍',        color: '#FFD400'},
  {key: 'bubble',       label: '말풍선',      color: '#FFFFFF'},
  {key: 'check',        label: '체크',        color: '#2FD873'},
  {key: 'cross',        label: '엑스',        color: '#FF3B30'},
];

const THUMB_BADGE_LIST = [
  // ★후킹 5개(2026-09-23 사장님 "영상 속 제품 클릭! / 해당 제품 바로 보러가기 / 영상 속 제품 할인받기 같은 걸 맨 위에") — 구매 유도 문구가 먼저
  {label: '영상 속 제품 클릭!',     color: '#FF2D5E'},
  {label: '해당 제품 바로 보러가기', color: '#1F7CFF'},
  {label: '영상 속 제품 할인받기',   color: '#FF8A00'},
  {label: '프로필 링크에서 구매',    color: '#7B2FF7'},
  {label: '지금 클릭하면 특가',      color: '#1FA84E'},
  {label: '진짜 봐야할 것', color: '#FF2D2D'},
  {label: '충격',          color: '#FF2D2D'},
  {label: '실화',          color: '#FF2D2D'},
  {label: '꿀팁',          color: '#1FA84E'},
  {label: '이건 몰랐지',    color: '#7B2FF7'},
  {label: '주목',          color: '#FF8A00'},
  {label: '레전드',        color: '#FF2D2D'},
  {label: '990원',         color: '#111111'},
];
Object.assign(window.SCENE_DECORATION_CATALOG,{shapeDraw:THUMB_SHAPES,shapes:THUMB_SHAPE_LIST,thumbnailBadges:THUMB_BADGE_LIST});
})();

// ★항목 한 개를 그리는 곳은 여기 하나다(관제 133, 2026-10-06) — 숏폼 미리보기·렌더(out/scene-style-decorations.js draw)와
//   구매링크 롱폼 화면(out/link-longform-stage.html)이 같이 부른다. W·H = 무대 크기(px), m = 항목({kind,l,t,w,h,…} 무대 기준 %).
(()=>{
const C=window.SCENE_DECORATION_CATALOG;
C.paint=function(el,m,W,H){
     Object.assign(el.style,{left:m.l+'%',top:m.t+'%',width:m.w+'%',height:m.h+'%',opacity:(m.op??100)/100,transform:`rotate(${m.rot||0}deg)`,borderRadius:m.shape==='ellipse'?'50%':m.shape==='pill'?'999px':m.shape==='rect'?'0':'12%'});
     if(m.kind==='emoji'){el.textContent=m.ch;el.style.fontSize=Math.min(W*m.w/100,H*m.h/100)*.9+'px';}
     else if(m.kind==='badge'){
       el.textContent=m.text;el.style.background=`linear-gradient(135deg,color-mix(in srgb,${m.color},white 20%),${m.color} 65%,color-mix(in srgb,${m.color},black 20%))`;el.style.color='white';el.style.fontSize=Math.min(H*m.h/100*.48,W*m.w/100/Math.max(1,m.text.length)*1.5)+'px';el.style.fontWeight='900';el.style.fontFamily='Pretendard,sans-serif';el.style.borderRadius='999px';el.style.boxShadow=`0 ${W*.008}px ${W*.025}px #0005,inset 0 1px 0 #ffffff66`;el.style.border='1px solid #ffffff44';
       el.style.whiteSpace='nowrap';el.style.fontSize=Math.min(H*m.h/100*.48,W*m.w/100*.86/Math.max(1,[...m.text].reduce((n,c)=>n+(/[\u0000-\u007f]/.test(c)?.55:1),0)))+'px';
       if(m.badgeStyle==='ticket'){el.style.borderRadius='5%';el.style.borderLeft='3px dashed #ffffff99';el.style.borderRight='3px dashed #ffffff99';}
       if(m.badgeStyle==='glass'){el.style.background=m.color+'99';el.style.backdropFilter='blur(8px)';}
       if(m.badgeStyle==='burst'){el.style.borderRadius='12%';el.style.clipPath='polygon(5% 0,95% 0,100% 25%,96% 50%,100% 75%,95% 100%,5% 100%,0 75%,4% 50%,0 25%)';}
     }
     else if(m.kind==='image'){const img=document.createElement('img');img.src=m.src;img.draggable=false;Object.assign(img.style,{width:'100%',height:'100%',objectFit:'contain',display:'block',pointerEvents:'none'});el.style.background='transparent';el.style.borderRadius='0';el.append(img);}
     else if(m.kind==='graphic'){
       const canvas=document.createElement('canvas');canvas.width=480;canvas.height=480;canvas.style.width='100%';canvas.style.height='100%';const ctx=canvas.getContext('2d');ctx.translate(240,240);ctx.shadowColor='#0008';ctx.shadowBlur=12;C.shapeDraw[m.graphic]?.(ctx,170,m.color);el.append(canvas);
     }
     else if(m.fx==='blur'||m.fx==='blurdark'){el.style.backdropFilter='blur(10px)';el.style.background=m.fx==='blurdark'?'#0008':'transparent';if(m.soft>=80)el.style.maskImage='radial-gradient(ellipse,black 45%,transparent 72%)';}
     else{el.style.background=m.fx==='fade'?`linear-gradient(90deg,transparent,${m.color} 20%,${m.color} 80%,transparent)`:m.color;}
};
C.animate=function(el,m,W){
     if(m.motion&&m.motion!=='none'){
       // 가리키기는 도형이 향한 방향으로 오간다(2026-09-18 사장님 "회전하면 가리키는 방향도 화살표 방향으로").
       //   CSS translate는 rotate보다 먼저 적용돼 늘 가로로만 움직였다 → 회전 각도만큼 돌린 px 벡터로 준다.
       const ang=(m.rot||0)*Math.PI/180,amp=el.getBoundingClientRect().width||W*m.w/100,vx=Math.cos(ang),vy=Math.sin(ang);
       const along=k=>`${(vx*amp*k).toFixed(1)}px ${(vy*amp*k).toFixed(1)}px`;
       const frames={point:[{translate:along(-.08)},{translate:along(.10)},{translate:along(-.08)}],pulse:[{scale:'.88'},{scale:'1.1'},{scale:'.88'}],spin:[{rotate:'0deg'},{rotate:'360deg'}],float:[{translate:'0 5%'},{translate:'0 -8%'},{translate:'0 5%'}],reveal:[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0 0 0)',offset:.65},{clipPath:'inset(0 0 0 0)'}]}[m.motion];
       if(frames)el.animate(frames,{duration:1200,iterations:Infinity,easing:m.motion==='spin'?'linear':'ease-in-out'});
     }
};
})();
