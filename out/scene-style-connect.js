(()=>{
  const api=window.sceneStyle;if(!api)return;
  const pane=document.querySelector('.layout-a .edit-pane'),tabs=pane.querySelector('.tool-tabs');
  tabs.innerHTML='<button class="active" data-editor-tab="text">문구/텍스트</button><button data-editor-tab="effects">효과</button>';
  pane.querySelector('.hook-motion')?.remove();
  pane.querySelector('details')?.remove();
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
    Object.assign(media.style,{top:'0',height:'100%',objectPosition:'center',transform:`scale(${z})`});
    focus.hidden=m==='none';
    const pw=preview.clientWidth,ph=preview.clientHeight,r=(h.r||.22)*pw,cx=(h.cx??.5)*pw,cy=((h.cy??.55)-g.media.top/100)*ph;
    Object.assign(focus.style,{width:r*2+'px',height:r*2+'px',left:cx-r+'px',top:cy-r+'px',boxShadow:m==='spot'?'0 0 0 3000px #0009':'none'});
    lens.hidden=m!=='zoom';if(lens.src!==media.src)lens.src=media.src;
    const mh=ph*g.media.height/100;
    Object.assign(lens.style,{width:pw+'px',height:mh+'px',left:r+pw/2-2*cx+'px',top:r+mh/2-2*cy+'px',transform:`scale(${z*2})`});
    if(lastIndex!==g.sceneIndex){lastIndex=g.sceneIndex;updateControls();}
  }
  function updateControls(){
    const e=api.effect(),h=e.highlight||{};
    effectsPanel.querySelectorAll('[data-effect]').forEach(el=>el.value=({zoom:e.zoom||1,radius:h.r||.22,cx:h.cx??.5,cy:h.cy??.55})[el.dataset.effect]);
    effectsPanel.querySelector('output').textContent=Math.round((e.zoom||1)*100)+'%';
    effectsPanel.querySelectorAll('[data-effect-mode]').forEach(b=>b.classList.toggle('active',b.dataset.effectMode===(h.on?h.mode:'none')));
    effectsPanel.querySelector('[data-highlight-controls]').hidden=!h.on;
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
    else if(ev.target.closest('[data-effects-reset]'))api.effect({});else return;
    updateControls();sync();
  });
  tabs.addEventListener('click',ev=>{const b=ev.target.closest('[data-editor-tab]');if(!b)return;const isText=b.dataset.editorTab==='text';textPanel.hidden=!isText;effectsPanel.hidden=isText;tabs.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));updateControls();});
  // 텍스트를 다시 그린 프레임에서 영상 영역과 효과도 함께 갱신한다.
  new MutationObserver(sync).observe(preview.querySelector('.precision-edit-layer'),{childList:true});
  addEventListener('resize',sync);sync();updateControls();
  const embedded=window.parent!==window;
  if(embedded){document.body.classList.add('scene-embedded');primary.textContent='이 영상에 적용';}
  else primary.textContent='현재 설정 저장';
  primary.addEventListener('click',()=>{
    if(saving)return;
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
      const status=pane.querySelector('[data-connection-status]');if(status)status.textContent=`실제 자막 ${context.scenes.length}개를 연결했습니다.`;
      if(headerStatus)headerStatus.textContent=`실제 자막 ${context.scenes.length}개 연결`;
      sync();
    }
    if(event.data?.type==='scene-style-saved'){
      saving=false;primary.disabled=false;primary.textContent=event.data.ok?'✓ 이 영상에 적용됨':'저장 실패 · 다시 적용';
      if(!event.data.ok)pane.querySelector('[data-connection-status]').textContent=event.data.error||'저장에 실패했습니다.';
    }
  });
  if(embedded)window.parent.postMessage({type:'scene-style-ready'},location.origin);
})();
