(()=>{
 const api=window.sceneStyle,catalog=window.SCENE_DECORATION_CATALOG;if(!api||!catalog)return;
 const panel=document.querySelector('.scene-effects-panel'),preview=document.querySelector('#a-live-preview');
 const box=document.createElement('section');box.className='scene-decoration-panel';
 box.innerHTML=`<details open class="dec-shopset"><summary>🛍 쇼핑 안내 세트</summary><p>아래쪽 가리키는 화살표 + 안내 배지를 한 번에 넣어요. 다시 누르면 새로 놓입니다(겹치지 않아요).</p><label class="dec-shopset-target">가리킬 곳 <select data-shopset-target><option value="link">구매링크 칸(왼쪽 맨 아래)</option><option value="sticker">쇼핑 스티커(예전 자리)</option></select></label><div class="dec-choices"><button type="button" data-shopset="last3">마지막 3장면에 넣기</button><button type="button" data-shopset="here">이 장면만</button><button type="button" data-shopset="clear">세트 빼기</button></div><small data-shopset-status></small></details>
 <details open><summary>가림막</summary><div class="dec-choices"><button data-add-mask="blur">흐림</button><button data-add-mask="fade">그라데이션</button></div></details>
 <details open><summary>스티커 · 도형 · 배지</summary><div class="dec-kit"><button data-dec-kit="sticker" class="active">😀 스티커</button><button data-dec-kit="shape">🎨 도형</button><button data-dec-kit="badge">🏷 배지</button></div><div data-kit="sticker"><div class="dec-categories"></div><div class="dec-stickers"></div></div><div data-kit="shape" hidden><p>움직이는 도형 · 눌러서 영상 위에 추가</p><div class="dec-shapes"></div></div><div data-kit="badge" hidden><p>문구와 색, 모양을 바꿀 수 있어요</p><div class="dec-my-badges" hidden></div><div class="dec-badges"></div></div></details>
 <div class="dec-items"></div><div class="dec-edit" hidden><p>화면에서 끌어 이동 · ↘ 손잡이로 크기 · ⟳ 손잡이로 회전</p><label data-badge-text>배지 문구<input data-dec="text" type="text" maxlength="24"></label><label data-badge-style>배지 모양<select data-dec="badgeStyle"><option value="pill">그라데이션 알약</option><option value="ticket">티켓</option><option value="glass">유리 배지</option><option value="burst">포인트 배지</option></select></label><button type="button" data-save-badge hidden>⭐ 이 배지를 내 버튼으로 저장</button><label data-motion-control>움직임<select data-dec="motion"><option value="none">없음</option><option value="point">가리키기</option><option value="pulse">두근두근</option><option value="spin">회전</option><option value="float">둥실둥실</option><option value="reveal">쓱 나타나기</option></select></label><label>크기<input data-dec="size" type="range" min="5" max="90" step="1"></label><label data-mask-height>높이<input data-dec="h" type="range" min="2" max="35" step="1"></label><label>회전<input data-dec="rot" type="range" min="-180" max="180" step="1"></label><label>투명도<input data-dec="op" type="range" min="10" max="100" step="1"></label><label data-mask-color>색상<input data-dec="color" type="color"></label><button data-dec-delete>선택한 항목 삭제</button></div>`;
 // ★로고(관제 065, 2026-10-01): 파일을 올려 장면 맨 위에 얹는다. 값의 주인 = masks[] 안 {kind:'image',src}. 렌더·썸네일·캡컷은 이 draw()를
 //   headless로 돌려 같은 그림을 얻는다. 파일은 out/장면꾸미기_로고/<계정>/ (편집기 http·렌더 file:// 둘 다 같은 상대 경로).
 const logoBox=document.createElement('details');logoBox.open=true;logoBox.className='dec-logo';
 logoBox.innerHTML='<summary>🏷 로고</summary><p>내 로고 그림을 올리면 장면 <b>맨 위</b>에 얹혀요(PNG·JPG·WEBP, 2MB). <b>모든 장면</b>으로 쓴 마지막 로고는 다음 작업에도 자동으로 들어가요. 내 프리셋에도 함께 담겨요.</p><div class="dec-choices dec-logo-scope"><button type="button" data-logo-scope="all">모든 장면</button><button type="button" data-logo-scope="one">이 장면만</button></div><div class="dec-choices"><label class="dec-logo-pick"><input type="file" accept="image/png,image/jpeg,image/webp" data-logo-file hidden>📂 파일 불러오기</label></div><div class="dec-my-logos"></div>';
 box.append(logoBox);
 panel.append(box);
 const itemList=box.querySelector('.dec-items');
 box.prepend(itemList);
 // 고른 항목의 조절 칸(크기·높이·회전·배지 문구)을 목록 바로 아래에 둔다 — 맨 아래에 있으면 스티커 목록에 가려
 //   '가림막 크기 조절이 없다·배지 문구를 못 바꾼다'로 보였다(2026-09-18 사장님).
 itemList.after(box.querySelector('.dec-edit'));
 const toolbar=document.createElement('div');toolbar.className='scene-decoration-toolbar';toolbar.hidden=true;
 toolbar.innerHTML='<span></span><button type="button" data-overlay-delete>삭제</button>';preview.append(toolbar);
 const layer=document.createElement('div');layer.className='scene-decorations';preview.append(layer);
 // ★로고 전용 층(관제 065): 워터마크(.scene-brand-layer z8)·제목보다 위(z9) — '썸네일에 적용할 때 맨 위'. 드래그는 아래 bindLayer로 두 층에 같이 건다.
 const layerTop=document.createElement('div');layerTop.className='scene-decorations scene-decorations-top';preview.append(layerTop);
 // 📱 유튜브 화면 자리 보기(관제 133, 2026-10-06 사장님 "채널명·제목·링크 자리를 볼 수 있게만 — 렌더에 있으면 유튜브에 올렸을 때 중복"):
 //   쇼츠를 폰에서 볼 때 유튜브가 영상 위에 얹는 것들의 자리. 값 = 영상(9:16) 기준 %, 실제 폰 캡처(390x966, 영상 y101~800)에서 잰 것.
 //   ★링크 칸은 이 폰에서 영상 아래 바깥(t>100)이다 — 영상 안에 그릴 수 없는 자리라 세트는 그 바로 위를 가리킨다.
 //   ★자리의 주인은 이 표 하나다. 겹쳐보기(ytDraw)와 쇼핑 안내 세트(shopSetItems)가 둘 다 이 표를 읽는다.
 //   ★편집 화면 전용 — 미리보기(#a-live-preview) 밖에 두고, 렌더(?qa=1·sceneStyleExporting)에서는 만들지도 않는다.
 //   ★화면이 두 가지다(2026-10-06 캡처 4장 실측, 영상 자리는 넷 다 같다): basic = 보통(3장) / comment = 맨 아래에 댓글창이 뜬 화면(1장) —
 //     댓글창이 뜨면 채널명·제목·알약 줄이 통째로 약 7.5% 위로 올라와 알약 줄이 영상 안으로 들어온다.
 //     「수수료 지급」 줄이 없는 영상은 basic 보다 채널명·제목이 약 3% 아래다(알약 줄은 같은 자리).
 const YT_SHORTS_UI={
   basic:{
     channel:{label:'채널명 · 구독',l:3.6,t:89.9,w:40,h:4},
     title:{label:'제목',l:3.6,t:95.3,w:78,h:2.8},
     link:{label:'🔗 링크 칸(구매링크)',l:3.6,t:102.5,w:63.9,h:3.7},
     buttons:{label:'좋아요·댓글·공유',l:87,t:54.5,w:10.5,h:43.5},
   },
   comment:{
     channel:{label:'채널명 · 구독',l:3.6,t:81.5,w:40,h:4.5},
     title:{label:'제목',l:3.6,t:87.6,w:78,h:2.8},
     link:{label:'🔗 링크 칸(구매링크)',l:3.6,t:95.3,w:63.9,h:3.2},
     comment:{label:'댓글 올리기…',l:3.6,t:101,w:78,h:4.6},
     buttons:{label:'좋아요·댓글·공유',l:87,t:54.5,w:10.5,h:43.5},
   },
 };
 const YT_MODES=['','basic','comment'],YT_MODE_LABEL={'':'📱 유튜브 화면 자리',basic:'📱 유튜브 화면 자리 · 기본',comment:'📱 유튜브 화면 자리 · 댓글창'};
 const YT_KEY='scene_style_yt_ui',ytAllowed=!new URLSearchParams(location.search).has('qa');
 let ytLayer=null,ytButton=null;
 const ytOn=()=>{try{const v=localStorage.getItem(YT_KEY);return v==='2'?'comment':v==='1'?'basic':''}catch{return ''}};   // '' = 끔
 function ytDraw(){
   if(!ytLayer)return;
   const on=window.sceneStyleExporting?'':ytOn();
   ytLayer.style.display=on?'block':'none';ytButton.setAttribute('aria-pressed',String(!!on));ytButton.textContent=YT_MODE_LABEL[on];ytButton.style.background=on?'#11B98C':'transparent';ytButton.style.color=on?'#04231b':'#dce8ec';
   preview.parentElement.style.marginBottom=on?Math.ceil(preview.offsetHeight*.075)+'px':'';   // 링크 칸이 영상 아래로 나가는 만큼 자리를 비운다
   if(!on)return;
   if(ytLayer.dataset.mode!==on){
     ytLayer.dataset.mode=on;ytLayer.replaceChildren();
     for(const [key,a] of Object.entries(YT_SHORTS_UI[on])){
       const el=document.createElement('div');el.dataset.ytUi=key;el.textContent=a.label;
       Object.assign(el.style,{position:'absolute',left:a.l+'%',top:a.t+'%',width:a.w+'%',height:a.h+'%',boxSizing:'border-box',display:'flex',alignItems:'center',justifyContent:key==='buttons'?'center':'flex-start',padding:'0 .5em',overflow:'hidden',whiteSpace:'nowrap',color:'#fff',textShadow:'0 1px 2px #000',border:'1.5px dashed '+(key==='link'?'#FFE600':'#7FE7FF'),background:key==='link'?'#FFE60055':'#00000066',borderRadius:key==='link'||key==='comment'?'999px':'6px'});
       if(key==='buttons')el.style.writingMode='vertical-rl';
       ytLayer.append(el);
     }
   }
   Object.assign(ytLayer.style,{left:preview.offsetLeft+'px',top:preview.offsetTop+'px',width:preview.offsetWidth+'px',height:preview.offsetHeight+'px',fontSize:Math.max(9,preview.offsetHeight*.019)+'px'});
 }
 function ytSet(mode){try{localStorage.setItem(YT_KEY,String(Math.max(0,YT_MODES.indexOf(mode))))}catch{}ytDraw();}
 if(ytAllowed){
   ytLayer=document.createElement('div');ytLayer.className='scene-yt-ui';
   Object.assign(ytLayer.style,{position:'absolute',zIndex:40,pointerEvents:'none',display:'none',fontFamily:'Pretendard,sans-serif',fontWeight:'700',lineHeight:'1'});
   preview.parentElement.append(ytLayer);
   ytButton=document.createElement('button');ytButton.type='button';ytButton.dataset.ytUiToggle='';
   ytButton.title='폰에서 쇼츠를 볼 때 채널명·제목·링크 칸이 놓이는 자리를 겹쳐 봅니다. 누를 때마다 기본 → 댓글창이 뜬 화면 → 끔. 편집 화면에만 보이고 영상에는 안 들어가요.';
   Object.assign(ytButton.style,{border:'1px solid #294451',borderRadius:'8px',padding:'6px 10px',fontSize:'12px',fontWeight:'700',cursor:'pointer',marginRight:'8px'});
   ytButton.addEventListener('click',()=>ytSet(YT_MODES[(YT_MODES.indexOf(ytOn())+1)%YT_MODES.length]));
   const seg=document.querySelector('[data-frame="hook"]')?.closest('.seg');
   if(seg)seg.before(ytButton);else box.querySelector('.dec-shopset').append(ytButton);
   if(window.ResizeObserver)new ResizeObserver(ytDraw).observe(preview);
   addEventListener('resize',ytDraw);ytDraw();
 }
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
   list.forEach((m,i)=>{const row=document.createElement('div');row.className='dec-item';const label=m.kind==='emoji'?m.ch:m.kind==='image'?'🏷 로고':m.kind==='badge'?m.text:m.kind==='graphic'?(catalog.shapes.find(s=>s.key===m.graphic)?.label||'도형'):'가림막';const b=button(`${i+1}. ${label}`,'data-dec-select',i);b.classList.toggle('active',selected===i);const del=button('×','data-dec-remove',i);del.setAttribute('aria-label',`${i+1}. ${label} 삭제`);row.append(b,del);items.append(row)});
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
   const el=preview.querySelector(`[data-dec-index="${i}"]`),m=masks()[i];if(!el||!m||m.kind!=='badge')return;
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
   layer.replaceChildren();layerTop.replaceChildren();
   handles.hidden=true;
   const _order=[...masks().keys()].sort((x,y)=>(masks()[x].kind==='image')-(masks()[y].kind==='image'));   // 로고(image)는 늘 맨 위 — 나중에 그린다
   _order.forEach(i=>{const m=masks()[i];
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
     else if(m.kind==='image'){const img=document.createElement('img');img.src=m.src;img.draggable=false;Object.assign(img.style,{width:'100%',height:'100%',objectFit:'contain',display:'block',pointerEvents:'none'});el.style.background='transparent';el.style.borderRadius='0';el.append(img);}
     else if(m.kind==='graphic'){
       const canvas=document.createElement('canvas');canvas.width=480;canvas.height=480;canvas.style.width='100%';canvas.style.height='100%';const ctx=canvas.getContext('2d');ctx.translate(240,240);ctx.shadowColor='#0008';ctx.shadowBlur=12;catalog.shapeDraw[m.graphic]?.(ctx,170,m.color);el.append(canvas);
     }
     else if(m.fx==='blur'||m.fx==='blurdark'){el.style.backdropFilter='blur(10px)';el.style.background=m.fx==='blurdark'?'#0008':'transparent';if(m.soft>=80)el.style.maskImage='radial-gradient(ellipse,black 45%,transparent 72%)';}
     else{el.style.background=m.fx==='fade'?`linear-gradient(90deg,transparent,${m.color} 20%,${m.color} 80%,transparent)`:m.color;}
     (m.kind==='image'?layerTop:layer).append(el);
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
 // 🛍 쇼핑 안내 세트(2026-09-23 사장님 "화살표랑 문구를 일일이 배치하기 힘드니 세트 버튼 — 23·24·25 세 장면에"):
 //   유튜브 쇼핑 스티커가 기본으로 뜨는 왼쪽 아래를 가리키는 굵은 화살표 + 「영상 속 제품 클릭!」 배지.
 //   set 표식으로 묶어서 다시 누르면 옛 세트를 지우고 새로 놓는다(쌓이지 않게). 놓은 뒤엔 보통 항목처럼 끌어 고친다.
 const SHOPSET='shopcta';
 // 가리킬 곳(관제 133): link = 「관련 동영상」 링크 칸(구매링크 롱폼으로 가는 자리) / sticker = 예전 자리(쇼핑 스티커).
 //   link 자리는 YT_SHORTS_UI 에서 계산한다 — 화살표 끝(가리키기 움직임 포함)이 두 화면 중 더 높은 채널명 줄(댓글창 화면) 바로 위에서 멈춘다(그 아래는 유튜브 글자에 가린다).
 function shopSetItems(target){
   const base={shape:'round',fx:'solid',op:100,soft:30,set:SHOPSET};
   if(target==='sticker'){
     const label='영상 속 제품 클릭!',color=catalog.thumbnailBadges.find(x=>x.label===label)?.color||'#FF2D5E';
     return [
       {...base,kind:'graphic',graphic:'arrow_bold',l:1,t:43,w:30,h:16.875,color:'#FF3B30',rot:90,motion:'point'},
       {...base,kind:'badge',text:label,l:3,t:79,w:48,h:6,color,badgeStyle:'pill',rot:0,motion:'none'},
     ];
   }
   // 화살표 상자 = 가로 30%·세로 16.875%(정사각). 그림은 가운데에서 아래로 상자 높이의 22%(끝)·위로 25%(꼬리)까지, 움직임은 아래 +10%·위 -8%(가로 기준).
   const H=16.875,sway=30*9/16,tipMax=Math.min(...Object.values(YT_SHORTS_UI).map(v=>v.channel.t))-2,cy=tipMax-H*.22-sway*.10,top=cy-H*.25-sway*.08;
   const r=n=>Math.round(n*100)/100;
   return [
     {...base,kind:'graphic',graphic:'arrow_bold',l:1,t:r(cy-H/2),w:30,h:H,color:'#FF3B30',rot:90,motion:'point'},
     {...base,kind:'badge',text:'아래 구매링크 클릭!',l:3,t:r(top-7),w:48,h:6,color:'#FF2D5E',badgeStyle:'pill',rot:0,motion:'none'},
   ];
 }
 function shopSet(scope){
   const cur=api.geometry().sceneIndex,total=api.sceneCount?.()||0;
   const targets=scope==='last3'?[total-3,total-2,total-1].filter(i=>i>=1):scope==='clear'?Array.from({length:total},(_,i)=>i):[cur];   // 마지막 3장에 1장(훅)은 안 넣는다 · 빼기는 전 장면
   const items=shopSetItems(box.querySelector('[data-shopset-target]').value);
   let done=0,full=[];
   for(const i of targets){
     const keep=(api.effectAt(i).masks||[]).filter(m=>m.set!==SHOPSET);
     if(scope!=='clear'&&keep.length+2>12){full.push(i+1);continue;}
     api.effectAt(i,{...api.effectAt(i),masks:scope==='clear'?keep:[...keep,...items]});done++;
   }
   selected=-1;controls();draw();
   if(scope!=='clear'&&done&&ytLayer&&!ytOn())ytSet('basic');   // 넣은 자리가 유튜브 화면 어디인지 바로 보이게
   const nums=targets.map(i=>i+1).join('·');
   box.querySelector('[data-shopset-status]').textContent=(scope==='clear'?'모든 장면에서 세트를 뺐어요':`${nums}장에 넣었어요`)+(full.length?` (${full.join('·')}장은 항목이 12개라 못 넣음)`:'');
   return done;
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
   if(b.hasAttribute('data-shopset')){shopSet(b.dataset.shopset);return;}
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

 const addLogo=(src,w,h)=>{const list=structuredClone(masks());if(list.length>=12)return;const ratio=(h&&w)?h/w:1;const ww=24,hh=Math.min(40,ww*ratio*9/16);
   list.push({kind:'image',src,l:70,t:4,w:ww,h:hh,shape:'rect',fx:'solid',color:'#000000',op:100,soft:0,rot:0,motion:'none'});selected=list.length-1;commit(list);controls();draw();};
 const drawMyLogos=async()=>{const wrap=logoBox.querySelector('.dec-my-logos');try{const r=await fetch('/api/produce/scene-style/logo');const d=await r.json();const items=(d&&d.items)||[];
   wrap.replaceChildren(...items.map(it=>{const b=document.createElement('button');b.type='button';b.className='dec-my-logo';b.title='이 로고 얹기';const img=document.createElement('img');img.src=it.src;img.alt='';b.append(img);b.addEventListener('click',()=>addLogo(it.src));return b;}));
   wrap.hidden=!items.length;}catch(_){wrap.hidden=true;}};
 // 로고 범위(모든 장면 / 이 장면만) — 판단은 precision20-ui.js logoScope 한 곳, 여기는 버튼만 그린다.
  const syncLogoScope=()=>{const v=api.logoScope();logoBox.querySelectorAll('[data-logo-scope]').forEach(b=>b.classList.toggle('active',b.dataset.logoScope===v));};
  logoBox.addEventListener('click',e=>{const b=e.target.closest('[data-logo-scope]');if(!b)return;api.logoScope(b.dataset.logoScope);syncLogoScope();controls();draw();});
  syncLogoScope();
  if(location.protocol!=='file:')drawMyLogos();   // 렌더(file://)에선 목록이 필요 없다
 logoBox.querySelector('[data-logo-file]').addEventListener('change',async e=>{const f=e.target.files&&e.target.files[0];e.target.value='';if(!f)return;
   const fd=new FormData();fd.append('file',f);
   try{const r=await fetch('/api/produce/scene-style/logo',{method:'POST',body:fd});const d=await r.json();if(!r.ok||!d.ok){alert(d.error||'로고를 올리지 못했어요');return;}addLogo(d.src,d.w,d.h);drawMyLogos();}
   catch(_){alert('로고를 올리지 못했어요(연결)');}});
 box.addEventListener('input',event=>{
   const key=event.target.dataset.dec,list=structuredClone(masks()),m=list[selected];if(!key||!m)return;
   if(['color','text','motion','badgeStyle'].includes(key))m[key]=event.target.value;
   else if(key==='size'){const ratio=m.h/m.w;m.w=Math.min(100-m.l,Number(event.target.value));m.h=Math.min(100-m.t,m.w*ratio);}
   else m[key]=Number(event.target.value);
   if(key==='badgeStyle')m.fx=m.badgeStyle==='glass'?'blur':'solid';
   commit(list);draw();
 });
 const bindLayer=layer=>{
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
 };
 bindLayer(layer);bindLayer(layerTop);
 function removeSelected(){const list=structuredClone(masks());if(selected<0||selected>=list.length)return;list.splice(selected,1);selected=-1;drag=null;commit(list);controls();draw();}
 toolbar.querySelector('button').addEventListener('click',removeSelected);
 document.addEventListener('keydown',event=>{if(!['Delete','Backspace'].includes(event.key)||event.target.closest('input,textarea,select,[contenteditable="true"]')||panel.hidden)return;if(selected>=0){event.preventDefault();removeSelected();}});
 new MutationObserver(draw).observe(preview.querySelector('.precision-edit-layer'),{childList:true});
 addEventListener('resize',()=>{if(!window.sceneStyleExporting)draw()});picker();draw();
 window.sceneDecorations={motionAt(time){for(const el of layer.children)for(const animation of el.getAnimations()){animation.pause();animation.currentTime=time;}return masks().some(m=>m.motion&&m.motion!=='none')},refresh(){controls();draw();}};
})();
