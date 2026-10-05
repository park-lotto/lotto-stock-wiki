(()=>{
  const api=window.sceneStyle;if(!api)return;
  const pane=document.querySelector('.layout-a .edit-pane'),tabs=pane.querySelector('.tool-tabs');
  tabs.innerHTML='<button class="active" data-editor-tab="text">문구/텍스트</button><button data-editor-tab="effects">효과</button>';
  const titleMotion=pane.querySelector('.hook-motion');
  pane.querySelector(':scope > details')?.remove();
  const textPanel=document.createElement('div');textPanel.className='scene-text-panel';
  const primary=pane.querySelector('.primary'),save=pane.querySelector('.secondary');
  [...pane.children].filter(el=>![tabs,primary,save].includes(el)).forEach(el=>textPanel.append(el));
  tabs.after(textPanel);
  const effectsPanel=document.createElement('section');effectsPanel.className='scene-effects-panel';effectsPanel.hidden=true;
  effectsPanel.innerHTML=`<p>현재 장면의 영상에 적용합니다.</p>
    <label>화면 확대 <output data-effect-value="zoom"></output><input data-effect="zoom" type="range" min="1" max="3" step="0.05" value="1"></label>
    <div class="scene-effect-choices"><button data-effect-mode="none">없음</button><button data-effect-mode="zoom">돋보기</button><button data-effect-mode="spot">스포트라이트</button></div>
    <div data-highlight-controls><label>강조 크기<input data-effect="radius" type="range" min="0.06" max="0.45" step="0.01" value="0.22"></label>
    <label>가로 위치<input data-effect="cx" type="range" min="0.1" max="0.9" step="0.01" value="0.5"></label>
    <label>세로 위치<input data-effect="cy" type="range" min="0.1" max="0.9" step="0.01" value="0.55"></label></div>
    <button class="scene-effects-reset" data-effects-reset>이 장면 효과 초기화</button>`;
  textPanel.after(effectsPanel);
  const copyEffects=document.createElement('button');copyEffects.className='scene-effects-reset';copyEffects.textContent='이 효과를 다른 장면에도 적용';copyEffects.dataset.effectsAll='';effectsPanel.append(copyEffects);
  copyEffects.addEventListener('click',()=>{api.copyEffectsToAll();copyEffects.textContent='모든 장면에 적용했어요';setTimeout(()=>copyEffects.textContent='이 효과를 다른 장면에도 적용',1600);});
  // 장면 효과(관제 124) — 잘된 썰 쇼핑 채널 114편에서 실제로 쓰는 것만. 값은 api.refFx(실측·사장님 선택) 한 곳.
  //   아무 장면이든 켤 수 있고, 중요 장면(훅·제품 공개·고조·CTA — 서버 scene_style.moment_of 판단)엔 한 번에 켠다.
  const MOMENT_NAME={hook:'훅',reveal:'제품 공개',peak:'고조',cta:'CTA'};
  const pickMoments=new Set(Object.keys(MOMENT_NAME));
  const refBox=document.createElement('div');refBox.className='scene-ref-fx';
  refBox.innerHTML=`<p><b>강조 효과</b><br><small>잘된 쇼츠 114편 실측 · 이 장면: <b data-ref-moment>-</b></small></p>
    <button type="button" class="scene-effects-reset" data-ref-fx="zoom">이 장면 강조 확대 (2배)</button>
    <button type="button" class="scene-effects-reset" data-ref-fx="dim">이 장면 어둡게 강조</button>
    <p><b>중요 장면에 한 번에</b></p>
    <div class="scene-effect-choices">${Object.entries(MOMENT_NAME).map(([k,v])=>`<button type="button" class="active" data-ref-moment-pick="${k}">${v}</button>`).join('')}</div>
    <button type="button" class="scene-effects-reset" data-ref-fx="all-zoom">고른 장면에 강조 확대</button>
    <button type="button" class="scene-effects-reset" data-ref-fx="all-dim">고른 장면에 어둡게 강조</button>
    <p><b>영상 전체</b></p>
    <button type="button" class="scene-effects-reset" data-ref-fx="jump"></button>
    <button type="button" class="scene-effects-reset" data-ref-fx="title">시작 어두운 제목 화면</button>`;
  effectsPanel.append(refBox);
  // 고른 중요 장면이 전부 켜져 있으면 '끄기'로 보인다
  const allOn=kind=>{const ms=api.moments(),scenes=api.context()?.scenes||[];let prev=null,any=false,all=true;
    scenes.forEach((s,i)=>{const first=s.beat_idx!==prev;prev=s.beat_idx;if(first&&ms[i]&&pickMoments.has(ms[i])){any=true;all=all&&api.emphOn(i,kind);}});return any&&all;};
  function syncRefFx(){
    const i=api.geometry().sceneIndex,m=api.moments()[i];
    refBox.querySelector('[data-ref-moment]').textContent=m?MOMENT_NAME[m]:'일반';
    // 켜짐은 글자로 보인다 — 이 버튼 모양(scene-effects-reset)엔 켜짐 색이 없다(화면 캡처로 확인)
    const on=(sel,yes,label)=>{const b=refBox.querySelector(sel);b.classList.toggle('active',yes);b.textContent=label+(yes?' ✓ 켜짐':'');};
    on('[data-ref-fx="zoom"]',api.emphOn(i,'zoom'),'이 장면 강조 확대 (2배)');
    on('[data-ref-fx="dim"]',api.emphOn(i,'dim'),'이 장면 어둡게 강조');
    refBox.querySelectorAll('[data-ref-moment-pick]').forEach(b=>b.classList.toggle('active',pickMoments.has(b.dataset.refMomentPick)));
    refBox.querySelector('[data-ref-fx="all-zoom"]').textContent=allOn('zoom')?'고른 장면 강조 확대 끄기':'고른 장면에 강조 확대';
    refBox.querySelector('[data-ref-fx="all-dim"]').textContent=allOn('dim')?'고른 장면 어둡게 끄기':'고른 장면에 어둡게 강조';
    refBox.querySelector('[data-ref-fx="jump"]').textContent=api.jumpZoomOn()?'점프 줌 컷 빼기':'점프 줌 컷 넣기 (구절마다 1.35배)';
    const t=api.effectAt(0).dim;
    on('[data-ref-fx="title"]',!!t&&t.sec>0,'시작 어두운 제목 화면');
  }
  refBox.addEventListener('click',ev=>{
    const pick=ev.target.closest('[data-ref-moment-pick]');
    if(pick){const k=pick.dataset.refMomentPick;pickMoments.has(k)?pickMoments.delete(k):pickMoments.add(k);syncRefFx();return;}
    const b=ev.target.closest('[data-ref-fx]');if(!b)return;const fx=api.refFx,i=api.geometry().sceneIndex,what=b.dataset.refFx;
    if(what==='zoom'||what==='dim')api.emphAt(i,what,!api.emphOn(i,what));
    else if(what==='all-zoom'||what==='all-dim'){const kind=what.slice(4);api.emphMoments([...pickMoments],kind,!allOn(kind));}
    else if(what==='jump')api.jumpZoom(!api.jumpZoomOn());
    else{const e=structuredClone(api.effectAt(0));if(e.dim&&e.dim.sec>0)delete e.dim;else e.dim={...fx.dimTitle};api.effectAt(0,e);}
    updateControls();sync();
  });
  if(titleMotion)textPanel.querySelector('.ai-card').after(titleMotion);
  const note=textPanel.querySelector('.ai-card');if(note)note.innerHTML='<b>문구·자막 편집</b><br><span data-connection-status>저장한 설정으로 미리보고 있습니다.</span>';
  const preview=document.querySelector('#a-live-preview'),media=preview.querySelector('.precision-media');
  const windowEl=document.createElement('div');windowEl.className='scene-media-clip';media.before(windowEl);windowEl.append(media);
  const focus=document.createElement('div');focus.className='scene-focus';windowEl.append(focus);
  const lens=document.createElement('img');lens.className='scene-lens';focus.append(lens);
  const headerStatus=document.querySelector('[data-page="a"] .analysis');if(headerStatus)headerStatus.textContent='템플릿 미리보기';
  let lastIndex=-1,context=null,saving=false;
  function sync(){
    const g=api.geometry(),e=api.effect(),z=Number(e.zoom)||1,h=e.highlight||{},m=h.on?h.mode:'none';
    windowEl.style.top=g.media.top+'%';windowEl.style.height=g.media.height+'%';
    const px=(e.panX||0)*(z-1)*preview.clientWidth/2,py=(e.panY||0)*(z-1)*preview.clientHeight*g.media.height/200;
    // 어둡게(관제 124): 미리보기 그림 = 장면 첫 프레임 — 완성본(compose)·썸네일(compose_still)도 장면 시작에 같은 밝기를 건다.
    const dim=e.dim&&Number(e.dim.level)>0?Number(e.dim.level):1;
    Object.assign(media.style,{top:'0',height:'100%',objectPosition:'center',transform:`translate(${px}px,${py}px) scale(${z})`,filter:dim<1?`brightness(${dim})`:''});windowEl.style.cursor=z>1?'grab':'default';
    focus.hidden=m==='none';
    const pw=preview.clientWidth,ph=preview.clientHeight,r=(h.r||.22)*pw,cx=(h.cx??.5)*pw,cy=((h.cy??.55)-g.media.top/100)*ph;
    Object.assign(focus.style,{width:r*2+'px',height:r*2+'px',left:cx-r+'px',top:cy-r+'px',boxShadow:m==='spot'?'0 0 0 3000px #0009':'none'});
    lens.hidden=m!=='zoom';if(lens.src!==media.src)lens.src=media.src;
    const mh=ph*g.media.height/100;
    Object.assign(lens.style,{width:pw+'px',height:mh+'px',left:r+pw/2-2*cx+px*2+'px',top:r+mh/2-2*cy+py*2+'px',transform:`scale(${z*2})`});
    if(lastIndex!==g.sceneIndex){lastIndex=g.sceneIndex;updateControls();}
  }
  let mediaDrag=null;
  windowEl.addEventListener('pointerdown',event=>{if(event.button!==0)return;const isLens=!!event.target.closest('.scene-focus'),e=structuredClone(api.effect());if(!isLens&&(e.zoom||1)<=1)return;mediaDrag={id:event.pointerId,x:event.clientX,y:event.clientY,isLens,e,rect:preview.getBoundingClientRect()};windowEl.setPointerCapture(event.pointerId);event.preventDefault();});
  windowEl.addEventListener('pointermove',event=>{
    if(!mediaDrag||mediaDrag.id!==event.pointerId)return;const d=mediaDrag,e=structuredClone(d.e),dx=(event.clientX-d.x)/d.rect.width,dy=(event.clientY-d.y)/d.rect.height,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
    if(d.isLens)e.highlight={...e.highlight,cx:clamp((e.highlight.cx??.5)+dx,0,1),cy:clamp((e.highlight.cy??.55)+dy,0,1)};
    else{const z=e.zoom||1,mh=api.geometry().media.height/100;e.panX=clamp((e.panX||0)+dx*2/(z-1),-1,1);e.panY=clamp((e.panY||0)+dy*2/((z-1)*mh),-1,1);}
    api.effect(e);sync();updateControls();
  });
  for(const type of ['pointerup','pointercancel','lostpointercapture'])windowEl.addEventListener(type,()=>mediaDrag=null);
  windowEl.addEventListener('dragstart',event=>event.preventDefault());
  function updateControls(){
    const e=api.effect(),h=e.highlight||{};
    effectsPanel.querySelectorAll('[data-effect]').forEach(el=>el.value=({zoom:e.zoom||1,radius:h.r||.22,cx:h.cx??.5,cy:h.cy??.55})[el.dataset.effect]);
    effectsPanel.querySelector('output').textContent=Math.round((e.zoom||1)*100)+'%';
    effectsPanel.querySelectorAll('[data-effect-mode]').forEach(b=>b.classList.toggle('active',b.dataset.effectMode===(h.on?h.mode:'none')));
    effectsPanel.querySelector('[data-highlight-controls]').hidden=!h.on;
    syncRefFx();
  }
  effectsPanel.addEventListener('input',ev=>{
    const key=ev.target.dataset.effect;if(!key)return;
    const e=structuredClone(api.effect());if(key==='zoom')e.zoom=Number(ev.target.value);
    else{e.highlight=e.highlight||{on:true,mode:'zoom',shape:'circle',zoom:2};e.highlight[key==='radius'?'r':key]=Number(ev.target.value);}
    api.effect(e);updateControls();sync();
  });
  effectsPanel.addEventListener('click',ev=>{
    const b=ev.target.closest('[data-effect-mode]');
    if(b){const e=structuredClone(api.effect());e.highlight={cx:.5,cy:.55,r:.22,zoom:2,shape:'circle',...e.highlight,on:b.dataset.effectMode!=='none',mode:b.dataset.effectMode};api.effect(e);}
    else if(ev.target.closest('[data-effects-reset]')){api.effect({});window.sceneDecorations?.refresh();}else return;
    updateControls();sync();
  });
  tabs.addEventListener('click',ev=>{const b=ev.target.closest('[data-editor-tab]');if(!b)return;const isText=b.dataset.editorTab==='text';textPanel.hidden=!isText;effectsPanel.hidden=isText;tabs.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));updateControls();});
  // 텍스트를 다시 그린 프레임에서 영상 영역과 효과도 함께 갱신한다.
  new MutationObserver(sync).observe(preview.querySelector('.precision-edit-layer'),{childList:true});
  addEventListener('resize',sync);sync();updateControls();
  const embedded=window.parent!==window;
  save.hidden=true;
  if(embedded){document.body.classList.add('scene-embedded');primary.textContent='이 영상에 적용';}
  else primary.textContent='현재 설정 저장';
  primary.addEventListener('click',()=>{
    if(saving)return;
    const violations=api.validation?.()||[];
    if(violations.length){
      const status=pane.querySelector('[data-connection-status]');
      if(status)status.textContent=violations[0]+' 글씨를 줄이지 않고 원본 크기를 유지합니다.';
      primary.textContent='문구 길이를 확인해 주세요';
      setTimeout(()=>primary.textContent=embedded?'이 영상에 적용':'현재 설정 저장',1800);
      return;
    }
    if(!embedded){save.click();primary.textContent='✓ 현재 설정 저장됨';setTimeout(()=>primary.textContent='현재 설정 저장',1500);return;}
    if(!context)return;
    saving=true;primary.disabled=true;primary.textContent='영상에 저장 중…';
    window.parent.postMessage({type:'scene-style-save',jobId:context.jobId,snapshot:api.snapshot()},location.origin);
  });
  addEventListener('message',event=>{
    if(event.source!==window.parent||event.origin!==location.origin)return;
    if(event.data?.type==='scene-style-context'){
      context=event.data.context;
      const saved=event.data.snapshot||{...api.snapshot(),captionTexts:{},effects:{}};
      api.load(context,saved);
      if(Number.isInteger(event.data.sceneIndex))api.show(event.data.sceneIndex);
      document.documentElement.classList.remove('scene-waiting');   // 실제 데이터가 그려졌다 — 본문을 보인다(머리띠 가림은 html 표식이 계속)
      const status=pane.querySelector('[data-connection-status]');if(status)status.textContent=`실제 자막 ${context.scenes.length}개를 연결했습니다.`;
      if(headerStatus)headerStatus.textContent=`실제 자막 ${context.scenes.length}개 연결`;
      sync();
    }
    if(event.data?.type==='scene-style-saved'){
      saving=false;primary.disabled=false;primary.textContent=event.data.ok?'✓ 이 영상에 적용됨':'저장 실패 · 다시 적용';
      if(!event.data.ok)pane.querySelector('[data-connection-status]').textContent=event.data.error||'저장에 실패했습니다.';
      else save.click();
    }
  });
  // ★'원본 영상 그대로'로 바뀌면 부모(제작소)에게 알린다 — 그때는 새 편집기가 글자를 안 그리고
  //   렌더도 옛 경로(ffmpeg가 자막·헤드카피를 태운다)를 타므로, 제작소가 **옛 헤드카피·자막 칸**을 다시 보여 준다.
  //   (2026-09-24 사장님: "원본그대로 영상도 자막이나 문구등 원래 수정할 수 있는 거 아니었어?")
  if(embedded){
    const tell=()=>window.parent.postMessage({type:'scene-style-template',plain:document.body.classList.contains('no-template')},location.origin);
    window.addEventListener('scene-style-template',tell);
    window.parent.postMessage({type:'scene-style-ready'},location.origin);
    setTimeout(tell,0);
  }
})();
