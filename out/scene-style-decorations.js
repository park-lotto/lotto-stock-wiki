(()=>{
 const api=window.sceneStyle,catalog=window.SCENE_DECORATION_CATALOG;if(!api||!catalog)return;
 const panel=document.querySelector('.scene-effects-panel'),preview=document.querySelector('#a-live-preview');
 const box=document.createElement('section');box.className='scene-decoration-panel';
 box.innerHTML=`<details open><summary>가림막</summary><div class="dec-choices"><button data-add-mask="solid">단색</button><button data-add-mask="fade">그라데이션</button><button data-add-mask="blur">흐림</button><button data-add-mask="blurdark">흐림+어둡게</button></div></details>
 <details open><summary>스티커 · 도형 · 배지</summary><div class="dec-kit"><button data-dec-kit="sticker" class="active">😀 스티커</button><button data-dec-kit="shape">🎨 도형</button><button data-dec-kit="badge">🏷 배지</button></div><div data-kit="sticker"><div class="dec-categories"></div><div class="dec-stickers"></div></div><div data-kit="shape" hidden><p>움직이는 도형 · 눌러서 영상 위에 추가</p><div class="dec-shapes"></div></div><div data-kit="badge" hidden><p>문구와 색, 모양을 바꿀 수 있어요</p><div class="dec-badges"></div></div></details>
 <div class="dec-items"></div><div class="dec-edit" hidden><p>화면에서 끌어 이동하세요.</p><label data-badge-text>배지 문구<input data-dec="text" type="text" maxlength="24"></label><label data-badge-style>배지 모양<select data-dec="badgeStyle"><option value="pill">그라데이션 알약</option><option value="ticket">티켓</option><option value="glass">유리 배지</option><option value="burst">포인트 배지</option></select></label><label data-motion-control>움직임<select data-dec="motion"><option value="none">없음</option><option value="point">가리키기</option><option value="pulse">두근두근</option><option value="spin">회전</option><option value="float">둥실둥실</option><option value="reveal">쓱 나타나기</option></select></label><label>크기<input data-dec="size" type="range" min="5" max="90" step="1"></label><label data-mask-height>높이<input data-dec="h" type="range" min="2" max="35" step="1"></label><label>회전<input data-dec="rot" type="range" min="-45" max="45" step="1"></label><label>투명도<input data-dec="op" type="range" min="10" max="100" step="1"></label><label data-mask-color>색상<input data-dec="color" type="color"></label><button data-dec-delete>선택한 항목 삭제</button></div>`;
 panel.append(box);
 const layer=document.createElement('div');layer.className='scene-decorations';preview.append(layer);
 let selected=-1,category=0,index=-1,drag=null;
 const masks=()=>api.effect().masks||[];
 const commit=list=>api.effect({...api.effect(),masks:list});
 function button(label,attribute,value){const b=document.createElement('button');b.textContent=label;b.setAttribute(attribute,value);b.type='button';return b;}
 function picker(){
   const tabs=box.querySelector('.dec-categories'),grid=box.querySelector('.dec-stickers'),badges=box.querySelector('.dec-badges');tabs.replaceChildren();grid.replaceChildren();badges.replaceChildren();
   catalog.emoji.forEach(([name],i)=>{const b=button(name,'data-dec-category',i);b.classList.toggle('active',i===category);tabs.append(b)});
   catalog.emoji[category][1].forEach(ch=>grid.append(button(ch,'data-add-emoji',ch)));
   [...catalog.thumbnailBadges,...catalog.badges.filter(t=>!catalog.thumbnailBadges.some(b=>b.label===t)).map(label=>({label,color:'#FF2D5E'}))].forEach(def=>{const b=button(def.label,'data-add-badge',def.label);b.style.background=def.color;b.style.color='white';b.style.borderRadius='99px';badges.append(b)});
   const shapes=box.querySelector('.dec-shapes');shapes.replaceChildren();
   catalog.shapes.forEach(def=>{const b=button('','data-add-graphic',def.key),canvas=document.createElement('canvas');canvas.width=96;canvas.height=72;const ctx=canvas.getContext('2d');ctx.translate(48,36);catalog.shapeDraw[def.key](ctx,26,def.color);b.append(canvas,document.createTextNode(def.label));shapes.append(b)});
 }
 function controls(){
   const list=masks(),items=box.querySelector('.dec-items');items.replaceChildren();
   list.forEach((m,i)=>{const b=button(m.kind==='emoji'?m.ch:m.kind==='badge'?m.text:m.kind==='graphic'?(catalog.shapes.find(s=>s.key===m.graphic)?.label||'도형'):`가림막 ${i+1}`,'data-dec-select',i);b.classList.toggle('active',selected===i);items.append(b)});
   const edit=box.querySelector('.dec-edit'),m=list[selected];edit.hidden=!m;if(!m)return;
   edit.querySelectorAll('[data-dec]').forEach(el=>el.value=el.dataset.dec==='size'?m.w:m[el.dataset.dec]??0);
   edit.querySelector('[data-mask-height]').hidden=m.kind==='emoji';edit.querySelector('[data-mask-color]').hidden=m.kind==='emoji';
   edit.querySelector('[data-badge-text]').hidden=m.kind!=='badge';edit.querySelector('[data-badge-style]').hidden=m.kind!=='badge';edit.querySelector('[data-motion-control]').hidden=m.kind==='shape';
 }
 function draw(){
   const next=api.geometry().sceneIndex;if(index!==next){index=next;selected=-1;controls()}
   layer.replaceChildren();
   masks().forEach((m,i)=>{
     const el=document.createElement('div');el.className='scene-decoration';el.dataset.decIndex=i;el.classList.toggle('selected',selected===i);
     Object.assign(el.style,{left:m.l+'%',top:m.t+'%',width:m.w+'%',height:m.h+'%',opacity:(m.op??100)/100,transform:`rotate(${m.rot||0}deg)`,borderRadius:m.shape==='ellipse'?'50%':m.shape==='pill'?'999px':m.shape==='rect'?'0':'12%'});
     if(m.kind==='emoji'){el.textContent=m.ch;el.style.fontSize=Math.min(preview.clientWidth*m.w/100,preview.clientHeight*m.h/100)*.9+'px';}
     else if(m.kind==='badge'){
       el.textContent=m.text;el.style.background=`linear-gradient(135deg,color-mix(in srgb,${m.color},white 20%),${m.color} 65%,color-mix(in srgb,${m.color},black 20%))`;el.style.color='white';el.style.fontSize=Math.min(preview.clientHeight*m.h/100*.48,preview.clientWidth*m.w/100/Math.max(1,m.text.length)*1.5)+'px';el.style.fontWeight='900';el.style.fontFamily='Pretendard,sans-serif';el.style.borderRadius='999px';el.style.boxShadow=`0 ${preview.clientWidth*.008}px ${preview.clientWidth*.025}px #0005,inset 0 1px 0 #ffffff66`;el.style.border='1px solid #ffffff44';
       if(m.badgeStyle==='ticket'){el.style.borderRadius='5%';el.style.borderLeft='3px dashed #ffffff99';el.style.borderRight='3px dashed #ffffff99';}
       if(m.badgeStyle==='glass'){el.style.background=m.color+'99';el.style.backdropFilter='blur(8px)';}
       if(m.badgeStyle==='burst'){el.style.borderRadius='12%';el.style.clipPath='polygon(5% 0,95% 0,100% 25%,96% 50%,100% 75%,95% 100%,5% 100%,0 75%,4% 50%,0 25%)';}
     }
     else if(m.kind==='graphic'){
       const canvas=document.createElement('canvas');canvas.width=480;canvas.height=480;canvas.style.width='100%';canvas.style.height='100%';const ctx=canvas.getContext('2d');ctx.translate(240,240);ctx.shadowColor='#0008';ctx.shadowBlur=12;catalog.shapeDraw[m.graphic]?.(ctx,170,m.color);el.append(canvas);
     }
     else if(m.fx==='blur'||m.fx==='blurdark'){el.style.backdropFilter='blur(10px)';el.style.background=m.fx==='blurdark'?'#0008':'transparent';}
     else{el.style.background=m.fx==='fade'?`linear-gradient(90deg,transparent,${m.color} 20%,${m.color} 80%,transparent)`:m.color;}
     layer.append(el);
     if(m.motion&&m.motion!=='none'){
       const frames={point:[{translate:'-8% 0'},{translate:'10% 0'},{translate:'-8% 0'}],pulse:[{scale:'.88'},{scale:'1.1'},{scale:'.88'}],spin:[{rotate:'0deg'},{rotate:'360deg'}],float:[{translate:'0 5%'},{translate:'0 -8%'},{translate:'0 5%'}],reveal:[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0 0 0)',offset:.65},{clipPath:'inset(0 0 0 0)'}]}[m.motion];
       if(frames)el.animate(frames,{duration:1200,iterations:Infinity,easing:m.motion==='spin'?'linear':'ease-in-out'});
     }
   });
 }
 box.addEventListener('click',event=>{
   const b=event.target.closest('button');if(!b)return;
   if(b.hasAttribute('data-dec-kit')){box.querySelectorAll('[data-kit]').forEach(el=>el.hidden=el.dataset.kit!==b.dataset.decKit);box.querySelectorAll('[data-dec-kit]').forEach(el=>el.classList.toggle('active',el===b));return;}
   if(b.hasAttribute('data-dec-category')){category=Number(b.dataset.decCategory);picker();return;}
   const list=structuredClone(masks());
   if(b.hasAttribute('data-dec-select'))selected=Number(b.dataset.decSelect);
   else if(b.hasAttribute('data-dec-delete')){list.splice(selected,1);selected=-1;commit(list);}
   else{
     if(list.length>=12)return;
     let m={kind:'shape',l:6,t:70,w:88,h:12,shape:'round',fx:'solid',color:'#000000',op:100,soft:30,rot:0};
     if(b.hasAttribute('data-add-mask'))m.fx=b.dataset.addMask;
     else if(b.hasAttribute('data-add-emoji'))m={...m,kind:'emoji',ch:b.dataset.addEmoji,l:43,t:42,w:18,h:18*9/16};
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
   const target=event.target.closest('[data-dec-index]');if(!target||event.button!==0)return;
   selected=Number(target.dataset.decIndex);const m=masks()[selected];drag={x:event.clientX,y:event.clientY,l:m.l,t:m.t,id:event.pointerId};layer.setPointerCapture(event.pointerId);event.preventDefault();controls();draw();
 });
 layer.addEventListener('pointermove',event=>{
   if(!drag||event.pointerId!==drag.id)return;const list=structuredClone(masks()),m=list[selected],rect=preview.getBoundingClientRect();
   m.l=Math.max(0,Math.min(100-m.w,drag.l+(event.clientX-drag.x)/rect.width*100));m.t=Math.max(0,Math.min(100-m.h,drag.t+(event.clientY-drag.y)/rect.height*100));commit(list);draw();
 });
 for(const name of ['pointerup','pointercancel','lostpointercapture'])layer.addEventListener(name,()=>drag=null);
 new MutationObserver(draw).observe(preview.querySelector('.precision-edit-layer'),{childList:true});
 addEventListener('resize',draw);picker();draw();
 window.sceneDecorations={motionAt(time){for(const el of layer.children)for(const animation of el.getAnimations()){animation.pause();animation.currentTime=time;}return masks().some(m=>m.motion&&m.motion!=='none')},refresh:draw};
})();
