(()=>{
 const api=window.sceneStyle,catalog=window.SCENE_DECORATION_CATALOG;if(!api||!catalog)return;
 const panel=document.querySelector('.scene-effects-panel'),preview=document.querySelector('#a-live-preview');
 const box=document.createElement('section');box.className='scene-decoration-panel';
 box.innerHTML=`<details open><summary>가림막</summary><div class="dec-choices"><button data-add-mask="blur">흐림</button><button data-add-mask="fade">그라데이션</button></div></details>
 <details open><summary>스티커 · 도형 · 배지</summary><div class="dec-kit"><button data-dec-kit="sticker" class="active">😀 스티커</button><button data-dec-kit="shape">🎨 도형</button><button data-dec-kit="badge">🏷 배지</button></div><div data-kit="sticker"><div class="dec-categories"></div><div class="dec-stickers"></div></div><div data-kit="shape" hidden><p>움직이는 도형 · 눌러서 영상 위에 추가</p><div class="dec-shapes"></div></div><div data-kit="badge" hidden><p>문구와 색, 모양을 바꿀 수 있어요</p><div class="dec-my-badges" hidden></div><div class="dec-badges"></div></div></details>
 <div class="dec-items"></div><div class="dec-edit" hidden><p>화면에서 끌어 이동 · ↘ 손잡이로 크기 · ⟳ 손잡이로 회전</p><label data-badge-text>배지 문구<input data-dec="text" type="text" maxlength="24"></label><label data-badge-style>배지 모양<select data-dec="badgeStyle"><option value="pill">그라데이션 알약</option><option value="ticket">티켓</option><option value="glass">유리 배지</option><option value="burst">포인트 배지</option></select></label><button type="button" data-save-badge hidden>⭐ 이 배지를 내 버튼으로 저장</button><label data-motion-control>움직임<select data-dec="motion"><option value="none">없음</option><option value="point">가리키기</option><option value="pulse">두근두근</option><option value="spin">회전</option><option value="float">둥실둥실</option><option value="reveal">쓱 나타나기</option></select></label><label>크기<input data-dec="size" type="range" min="5" max="90" step="1"></label><label data-mask-height>높이<input data-dec="h" type="range" min="2" max="35" step="1"></label><label>회전<input data-dec="rot" type="range" min="-180" max="180" step="1"></label><label>투명도<input data-dec="op" type="range" min="10" max="100" step="1"></label><label data-mask-color>색상<input data-dec="color" type="color"></label><button data-dec-delete>선택한 항목 삭제</button></div>`;
 panel.append(box);
 const itemList=box.querySelector('.dec-items');
 box.prepend(itemList);
 // 고른 항목의 조절 칸(크기·높이·회전·배지 문구)을 목록 바로 아래에 둔다 — 맨 아래에 있으면 스티커 목록에 가려
 //   '가림막 크기 조절이 없다·배지 문구를 못 바꾼다'로 보였다(2026-09-18 사장님).
 itemList.after(box.querySelector('.dec-edit'));
 const toolbar=document.createElement('div');toolbar.className='scene-decoration-toolbar';toolbar.hidden=true;
 toolbar.innerHTML='<span></span><button type="button" data-overlay-delete>삭제</button>';preview.append(toolbar);
 const layer=document.createElement('div');layer.className='scene-decorations';preview.append(layer);
 let selected=-1,category=0,index=-1,drag=null;
 const masks=()=>api.effect().masks||[];
 const commit=list=>api.effect({...api.effect(),masks:list});
 // 내 배지(2026-09-22 사장님 '글자는 써서 저장 버튼으로 — 많이 쓰는 것들 해놓고 쓰라고'):
 //   배지를 하나 꾸민 뒤 저장하면 배지 목록 맨 위에 내 버튼으로 남는다. 문구·색·모양을 같이 기억한다.
 //   워터마크·광고 문구와 같은 방식으로 이 브라우저에 기억한다(다른 PC에는 안 따라간다). 최대 24개, 같은 문구는 새 것으로 바꾼다.
 const MY_BADGES='scene_style_my_badges',MY_BADGE_MAX=24;
 const myBadges=()=>{try{const v=JSON.parse(localStorage.getItem(MY_BADGES)||'[]');return Array.isArray(v)?v.filter(x=>x&&typeof x.text==='string'&&x.text.trim()).slice(0,MY_BADGE_MAX):[]}catch{return []}};
 const saveMyBadges=list=>{try{localStorage.setItem(MY_BADGES,JSON.stringify(list.slice(0,MY_BADGE_MAX)));return true}catch{return false}};
 function button(label,attribute,value){const b=document.createElement('button');b.textContent=label;b.setAttribute(attribute,value);b.type='button';return b;}
 function picker(){
   const tabs=box.querySelector('.dec-categories'),grid=box.querySelector('.dec-stickers'),badges=box.querySelector('.dec-badges');tabs.replaceChildren();grid.replaceChildren();badges.replaceChildren();
   catalog.emoji.forEach(([name],i)=>{const b=button(name,'data-dec-category',i);b.classList.toggle('active',i===category);tabs.append(b)});
   catalog.emoji[category][1].forEach(ch=>grid.append(button(ch,'data-add-emoji',ch)));
   [...catalog.thumbnailBadges,...catalog.badges.filter(t=>!catalog.thumbnailBadges.some(b=>b.label===t)).map(label=>({label,color:'#FF2D5E'}))].forEach(def=>{const b=button(def.label,'data-add-badge',def.label);b.style.background=def.color;b.style.color='white';b.style.borderRadius='99px';badges.append(b)});
   const mine=box.querySelector('.dec-my-badges'),saved=myBadges();mine.replaceChildren();mine.hidden=!saved.length;
   if(saved.length){const head=document.createElement('p');head.textContent='⭐ 내 배지 · 누르면 추가, ×로 지우기';mine.append(head);}
   saved.forEach((def,i)=>{const wrap=document.createElement('span');wrap.className='dec-my-badge';const b=button(def.text,'data-add-my-badge',i);b.style.background=def.color||'#FF2D5E';b.style.color='white';b.style.borderRadius='99px';
     const x=button('×','data-del-my-badge',i);x.title='내 배지에서 지우기';x.setAttribute('aria-label',def.text+' 지우기');wrap.append(b,x);mine.append(wrap)});
   const shapes=box.querySelector('.dec-shapes');shapes.replaceChildren();
   catalog.shapes.forEach(def=>{const b=button('','data-add-graphic',def.key),canvas=document.createElement('canvas');canvas.width=96;canvas.height=72;const ctx=canvas.getContext('2d');ctx.translate(48,36);catalog.shapeDraw[def.key](ctx,26,def.color);b.append(canvas,document.createTextNode(def.label));shapes.append(b)});
 }
 function controls(){
   const list=masks(),items=box.querySelector('.dec-items');items.replaceChildren();
   list.forEach((m,i)=>{const row=document.createElement('div');row.className='dec-item';const label=m.kind==='emoji'?m.ch:m.kind==='badge'?m.text:m.kind==='graphic'?(catalog.shapes.find(s=>s.key===m.graphic)?.label||'도형'):'가림막';const b=button(`${i+1}. ${label}`,'data-dec-select',i);b.classList.toggle('active',selected===i);const del=button('×','data-dec-remove',i);del.setAttribute('aria-label',`${i+1}. ${label} 삭제`);row.append(b,del);items.append(row)});
   toolbar.hidden=!list[selected];toolbar.querySelector('span').textContent=list[selected]?`${selected+1}번 선택`:'';
   const edit=box.querySelector('.dec-edit'),m=list[selected];edit.hidden=!m;if(!m)return;
   edit.querySelectorAll('[data-dec]').forEach(el=>el.value=el.dataset.dec==='size'?m.w:m[el.dataset.dec]??0);
   edit.querySelectorAll('label').forEach(l=>l.hidden=false);   // 항목 종류가 바뀔 때 앞 항목의 숨김이 남지 않게 먼저 전부 보이게
   edit.querySelector('[data-mask-height]').hidden=m.kind==='emoji';edit.querySelector('[data-mask-color]').hidden=m.kind==='emoji';
   edit.querySelector('[data-badge-text]').hidden=m.kind!=='badge';edit.querySelector('[data-badge-style]').hidden=m.kind!=='badge';edit.querySelector('[data-save-badge]').hidden=m.kind!=='badge';edit.querySelector('[data-motion-control]').hidden=m.kind==='shape';
   // 가림막은 투명도만(2026-09-18 사장님). 크기·위치는 화면 손잡이와 끌기로 한다.
   const isMask=m.kind==='shape';
   edit.querySelectorAll('label').forEach(l=>{if(isMask)l.hidden=!l.querySelector('[data-dec="op"]');});
 }
 // 화면에서 바로 고치기(2026-09-18 사장님 "여기서 직접 수정되게 편하게"): 고른 항목에 손잡이 두 개.
 //   ↘ 오른쪽 아래 = 크기(가림막은 가로·세로 따로, 나머지는 비율 유지) / ⟳ 위 = 회전. 렌더 때는 그리지 않는다.
 const handles=document.createElement('div');handles.className='scene-decoration-toolbar scene-decoration-handles';handles.hidden=true;
 handles.innerHTML='<button type="button" data-handle="resize" title="끌어서 크기">↘</button><button type="button" data-handle="rotate" title="끌어서 회전">⟳</button>';
 // 도구막대 클래스를 같이 달아(카메라 층 밖에 두려고) 어두운 배경·테두리까지 물려받아 화면 전체가 덮였다(2026-09-18 실측) → 지운다.
 Object.assign(handles.style,{position:'absolute',inset:'0',pointerEvents:'none',zIndex:30,background:'transparent',border:'0',padding:'0',boxShadow:'none'});
 handles.querySelectorAll('button').forEach(b=>Object.assign(b.style,{position:'absolute',width:'26px',height:'26px',marginLeft:'-13px',marginTop:'-13px',borderRadius:'50%',border:'2px solid #fff',background:'#11B98C',color:'#fff',fontSize:'14px',lineHeight:'1',padding:'0',cursor:b.dataset.handle==='resize'?'nwse-resize':'grab',pointerEvents:'auto',boxShadow:'0 2px 6px #0007'}));
 preview.append(handles);
 function placeHandles(m){
   const W=preview.clientWidth,H=preview.clientHeight,cx=(m.l+m.w/2)/100*W,cy=(m.t+m.h/2)/100*H,a=(m.rot||0)*Math.PI/180;
   const at=(dx,dy)=>[cx+dx*Math.cos(a)-dy*Math.sin(a),cy+dx*Math.sin(a)+dy*Math.cos(a)];
   const [rx,ry]=at(m.w/200*W,m.h/200*H),[tx,ty]=at(0,-m.h/200*H-22);
   Object.assign(handles.querySelector('[data-handle="resize"]').style,{left:rx+'px',top:ry+'px'});
   Object.assign(handles.querySelector('[data-handle="rotate"]').style,{left:tx+'px',top:ty+'px'});
   handles.hidden=false;
 }
 let grab=null;
 handles.addEventListener('pointerdown',event=>{
   const h=event.target.closest('[data-handle]');if(!h||selected<0)return;const m=masks()[selected];if(!m)return;
   const rect=preview.getBoundingClientRect();grab={kind:h.dataset.handle,id:event.pointerId,m:structuredClone(m),cx:rect.left+(m.l+m.w/2)/100*rect.width,cy:rect.top+(m.t+m.h/2)/100*rect.height,rect};
   h.setPointerCapture(event.pointerId);event.preventDefault();event.stopPropagation();
 });
 handles.addEventListener('pointermove',event=>{
   if(!grab||event.pointerId!==grab.id)return;const list=structuredClone(masks()),m=list[selected];if(!m)return;
   if(grab.kind==='rotate'){let deg=Math.atan2(event.clientY-grab.cy,event.clientX-grab.cx)*180/Math.PI+90;if(deg>180)deg-=360;m.rot=Math.round(deg);}
   else{
     // 회전을 되돌린 좌표에서 가운데~손잡이 거리 = 반폭·반높이
     const a=-(grab.m.rot||0)*Math.PI/180,dx=event.clientX-grab.cx,dy=event.clientY-grab.cy,ux=dx*Math.cos(a)-dy*Math.sin(a),uy=dx*Math.sin(a)+dy*Math.cos(a);
     let w=Math.max(4,Math.abs(ux)*2/grab.rect.width*100),h=Math.max(2,Math.abs(uy)*2/grab.rect.height*100);
     if(m.kind!=='shape'){const ratio=grab.m.h/grab.m.w;h=w*ratio;}
     w=Math.min(100,w);h=Math.min(100,h);
     m.l=Math.max(0,Math.min(100-w,grab.m.l+grab.m.w/2-w/2));m.t=Math.max(0,Math.min(100-h,grab.m.t+grab.m.h/2-h/2));m.w=w;m.h=h;
   }
   commit(list);draw();controls();
 });
 for(const name of ['pointerup','pointercancel','lostpointercapture'])handles.addEventListener(name,()=>grab=null);
 // 배지 글자 바로 고치기 — 끌기 시작(pointerdown)에서 요소를 다시 그리므로 브라우저 click/dblclick이 아예 안 뜬다
 //   (누름·뗌이 같은 요소여야 click이 난다). 그래서 같은 항목을 0.4초 안에 두 번 누르면 편집으로 본다.
 let lastTap={i:-1,t:0};
 function editBadge(i){
   const el=layer.querySelector(`[data-dec-index="${i}"]`),m=masks()[i];if(!el||!m||m.kind!=='badge')return;
   drag=null;el.contentEditable='true';el.style.cursor='text';el.style.outline='2px dashed #fff';el.focus();document.getSelection().selectAllChildren(el);
   editing=true;
   const done=()=>{editing=false;el.contentEditable='false';const text=el.textContent.trim().slice(0,24);if(text&&text!==m.text){const list=structuredClone(masks());list[i].text=text;commit(list);}controls();draw();};
   el.addEventListener('blur',done,{once:true});
   el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key==='Escape'){e.preventDefault();el.blur();}e.stopPropagation();});
 }
 let editing=false;
 function draw(){
   if(editing)return;
   const next=api.geometry().sceneIndex;if(index!==next){index=next;selected=-1;controls()}
   layer.replaceChildren();
   handles.hidden=true;
   masks().forEach((m,i)=>{
     const el=document.createElement('div');el.className='scene-decoration';el.dataset.decIndex=i;el.classList.toggle('selected',selected===i);
     Object.assign(el.style,{left:m.l+'%',top:m.t+'%',width:m.w+'%',height:m.h+'%',opacity:(m.op??100)/100,transform:`rotate(${m.rot||0}deg)`,borderRadius:m.shape==='ellipse'?'50%':m.shape==='pill'?'999px':m.shape==='rect'?'0':'12%'});
     if(m.kind==='emoji'){el.textContent=m.ch;el.style.fontSize=Math.min(preview.clientWidth*m.w/100,preview.clientHeight*m.h/100)*.9+'px';}
     else if(m.kind==='badge'){
       el.textContent=m.text;el.style.background=`linear-gradient(135deg,color-mix(in srgb,${m.color},white 20%),${m.color} 65%,color-mix(in srgb,${m.color},black 20%))`;el.style.color='white';el.style.fontSize=Math.min(preview.clientHeight*m.h/100*.48,preview.clientWidth*m.w/100/Math.max(1,m.text.length)*1.5)+'px';el.style.fontWeight='900';el.style.fontFamily='Pretendard,sans-serif';el.style.borderRadius='999px';el.style.boxShadow=`0 ${preview.clientWidth*.008}px ${preview.clientWidth*.025}px #0005,inset 0 1px 0 #ffffff66`;el.style.border='1px solid #ffffff44';
       el.style.whiteSpace='nowrap';el.style.fontSize=Math.min(preview.clientHeight*m.h/100*.48,preview.clientWidth*m.w/100*.86/Math.max(1,[...m.text].reduce((n,c)=>n+(/[\u0000-\u007f]/.test(c)?.55:1),0)))+'px';
       if(m.badgeStyle==='ticket'){el.style.borderRadius='5%';el.style.borderLeft='3px dashed #ffffff99';el.style.borderRight='3px dashed #ffffff99';}
       if(m.badgeStyle==='glass'){el.style.background=m.color+'99';el.style.backdropFilter='blur(8px)';}
       if(m.badgeStyle==='burst'){el.style.borderRadius='12%';el.style.clipPath='polygon(5% 0,95% 0,100% 25%,96% 50%,100% 75%,95% 100%,5% 100%,0 75%,4% 50%,0 25%)';}
     }
     else if(m.kind==='graphic'){
       const canvas=document.createElement('canvas');canvas.width=480;canvas.height=480;canvas.style.width='100%';canvas.style.height='100%';const ctx=canvas.getContext('2d');ctx.translate(240,240);ctx.shadowColor='#0008';ctx.shadowBlur=12;catalog.shapeDraw[m.graphic]?.(ctx,170,m.color);el.append(canvas);
     }
     else if(m.fx==='blur'||m.fx==='blurdark'){el.style.backdropFilter='blur(10px)';el.style.background=m.fx==='blurdark'?'#0008':'transparent';if(m.soft>=80)el.style.maskImage='radial-gradient(ellipse,black 45%,transparent 72%)';}
     else{el.style.background=m.fx==='fade'?`linear-gradient(90deg,transparent,${m.color} 20%,${m.color} 80%,transparent)`:m.color;}
     layer.append(el);
     if(selected===i&&!window.sceneStyleExporting)placeHandles(m);
     if(m.motion&&m.motion!=='none'){
       // 가리키기는 도형이 향한 방향으로 오간다(2026-09-18 사장님 "회전하면 가리키는 방향도 화살표 방향으로").
       //   CSS translate는 rotate보다 먼저 적용돼 늘 가로로만 움직였다 → 회전 각도만큼 돌린 px 벡터로 준다.
       const ang=(m.rot||0)*Math.PI/180,amp=el.getBoundingClientRect().width||preview.clientWidth*m.w/100,vx=Math.cos(ang),vy=Math.sin(ang);
       const along=k=>`${(vx*amp*k).toFixed(1)}px ${(vy*amp*k).toFixed(1)}px`;
       const frames={point:[{translate:along(-.08)},{translate:along(.10)},{translate:along(-.08)}],pulse:[{scale:'.88'},{scale:'1.1'},{scale:'.88'}],spin:[{rotate:'0deg'},{rotate:'360deg'}],float:[{translate:'0 5%'},{translate:'0 -8%'},{translate:'0 5%'}],reveal:[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0 0 0)',offset:.65},{clipPath:'inset(0 0 0 0)'}]}[m.motion];
       if(frames)el.animate(frames,{duration:1200,iterations:Infinity,easing:m.motion==='spin'?'linear':'ease-in-out'});
     }
   });
 }
 box.addEventListener('click',event=>{
   const b=event.target.closest('button');if(!b)return;
   if(b.hasAttribute('data-dec-kit')){box.querySelectorAll('[data-kit]').forEach(el=>el.hidden=el.dataset.kit!==b.dataset.decKit);box.querySelectorAll('[data-dec-kit]').forEach(el=>el.classList.toggle('active',el===b));return;}
   if(b.hasAttribute('data-dec-category')){category=Number(b.dataset.decCategory);picker();return;}
   if(b.hasAttribute('data-del-my-badge')){const mine=myBadges();mine.splice(Number(b.dataset.delMyBadge),1);saveMyBadges(mine);picker();return;}
   if(b.hasAttribute('data-save-badge')){
     const m=masks()[selected];if(!m||m.kind!=='badge'||!String(m.text||'').trim())return;
     const text=String(m.text).trim().slice(0,24),def={text,color:m.color||'#FF2D5E',badgeStyle:m.badgeStyle||'pill'};
     const ok=saveMyBadges([def,...myBadges().filter(x=>x.text!==text)]);picker();
     b.textContent=ok?'✓ 내 배지에 저장했습니다':'저장하지 못했습니다(브라우저 저장 공간)';setTimeout(()=>{b.textContent='⭐ 이 배지를 내 버튼으로 저장'},1600);return;
   }
   const list=structuredClone(masks());
   if(b.hasAttribute('data-dec-select'))selected=Number(b.dataset.decSelect);
   else if(b.hasAttribute('data-dec-remove')){const removed=Number(b.dataset.decRemove);list.splice(removed,1);selected=removed===selected?-1:selected>removed?selected-1:selected;commit(list);}
   else if(b.hasAttribute('data-dec-delete')){list.splice(selected,1);selected=-1;commit(list);}
   else{
     if(list.length>=12)return;
     let m={kind:'shape',l:6,t:70,w:88,h:12,shape:'round',fx:'solid',color:'#000000',op:100,soft:30,rot:0};
     if(b.hasAttribute('data-add-mask')){m.fx=b.dataset.addMask;if(m.fx==='fade'){m.fx='blur';m.soft=80;}}
     else if(b.hasAttribute('data-add-emoji'))m={...m,kind:'emoji',ch:b.dataset.addEmoji,l:43,t:42,w:18,h:18*9/16};
     else if(b.hasAttribute('data-add-my-badge')){const def=myBadges()[Number(b.dataset.addMyBadge)];if(!def)return;m={...m,kind:'badge',text:def.text,l:6,t:42,w:Math.min(60,18+def.text.length*3),h:7,color:def.color,badgeStyle:def.badgeStyle||'pill',motion:'none'};}
     else if(b.hasAttribute('data-add-badge'))m={...m,kind:'badge',text:b.dataset.addBadge,l:6,t:42,w:Math.min(60,18+b.dataset.addBadge.length*3),h:7,color:catalog.thumbnailBadges.find(x=>x.label===b.dataset.addBadge)?.color||'#FF2D5E',badgeStyle:'pill',motion:'none'};
     else if(b.hasAttribute('data-add-graphic')){const def=catalog.shapes.find(s=>s.key===b.dataset.addGraphic);m={...m,kind:'graphic',graphic:def.key,l:35,t:40,w:30,h:30*9/16,color:def.color,motion:def.key==='arrow_circle'?'spin':def.key.startsWith('arrow')?'point':def.key==='swoosh'||def.key==='check'?'reveal':def.key==='bubble'?'float':'pulse'};}
     else return;
     list.push(m);selected=list.length-1;commit(list);
   }
   controls();draw();
 });
 box.addEventListener('input',event=>{
   const key=event.target.dataset.dec,list=structuredClone(masks()),m=list[selected];if(!key||!m)return;
   if(['color','text','motion','badgeStyle'].includes(key))m[key]=event.target.value;
   else if(key==='size'){const ratio=m.h/m.w;m.w=Math.min(100-m.l,Number(event.target.value));m.h=Math.min(100-m.t,m.w*ratio);}
   else m[key]=Number(event.target.value);
   if(key==='badgeStyle')m.fx=m.badgeStyle==='glass'?'blur':'solid';
   commit(list);draw();
 });
 layer.addEventListener('pointerdown',event=>{
   if(event.button!==0)return;
   // Transparent canvas padding must not intercept a different decoration below it.
   const target=document.elementsFromPoint(event.clientX,event.clientY).map(e=>e.closest?.('[data-dec-index]')).filter((e,i,a)=>e&&a.indexOf(e)===i).find(el=>{
     const canvas=el.querySelector('canvas');if(!canvas)return true;
     const style=getComputedStyle(el),rect=el.getBoundingClientRect();
     let matrix=new DOMMatrix(style.transform==='none'?undefined:style.transform);
     const rotation=parseFloat(style.rotate)||0,scale=(style.scale==='none'?'1':style.scale).split(' ').map(Number);
     matrix=new DOMMatrix().rotate(rotation).scale(scale[0],scale[1]||scale[0]).multiply(matrix);
     const p=new DOMPoint(event.clientX-rect.left-rect.width/2,event.clientY-rect.top-rect.height/2).matrixTransform(matrix.inverse());
     const x=Math.floor((p.x/el.clientWidth+.5)*canvas.width),y=Math.floor((p.y/el.clientHeight+.5)*canvas.height);
     return x>=0&&y>=0&&x<canvas.width&&y<canvas.height&&canvas.getContext('2d').getImageData(x,y,1,1).data[3]>24;
   });
   if(!target)return;
   if(editing)return;
   const hit=Number(target.dataset.decIndex),now=performance.now();
   if(lastTap.i===hit&&now-lastTap.t<400&&masks()[hit]?.kind==='badge'){lastTap={i:-1,t:0};selected=hit;controls();draw();editBadge(hit);event.preventDefault();return;}
   lastTap={i:hit,t:now};
   selected=hit;const m=masks()[selected];drag={x:event.clientX,y:event.clientY,l:m.l,t:m.t,id:event.pointerId};layer.setPointerCapture(event.pointerId);event.preventDefault();controls();draw();
 });
 layer.addEventListener('pointermove',event=>{
   if(!drag||event.pointerId!==drag.id)return;const list=structuredClone(masks()),m=list[selected],rect=preview.getBoundingClientRect();
   m.l=Math.max(0,Math.min(100-m.w,drag.l+(event.clientX-drag.x)/rect.width*100));m.t=Math.max(0,Math.min(100-m.h,drag.t+(event.clientY-drag.y)/rect.height*100));commit(list);draw();
 });
 for(const name of ['pointerup','pointercancel','lostpointercapture'])layer.addEventListener(name,()=>drag=null);
 function removeSelected(){const list=structuredClone(masks());if(selected<0||selected>=list.length)return;list.splice(selected,1);selected=-1;drag=null;commit(list);controls();draw();}
 toolbar.querySelector('button').addEventListener('click',removeSelected);
 document.addEventListener('keydown',event=>{if(!['Delete','Backspace'].includes(event.key)||event.target.closest('input,textarea,select,[contenteditable="true"]')||panel.hidden)return;if(selected>=0){event.preventDefault();removeSelected();}});
 new MutationObserver(draw).observe(preview.querySelector('.precision-edit-layer'),{childList:true});
 addEventListener('resize',()=>{if(!window.sceneStyleExporting)draw()});picker();draw();
 window.sceneDecorations={motionAt(time){for(const el of layer.children)for(const animation of el.getAnimations()){animation.pause();animation.currentTime=time;}return masks().some(m=>m.motion&&m.motion!=='none')},refresh(){controls();draw();}};
})();
