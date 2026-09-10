(()=>{
  const rows=window.PRECISION20||[];
  const root=document;
  const preview=root.getElementById('a-live-preview');
  const grid=root.querySelector('.layout-a .preset-grid');
  if(!rows.length||!preview||!grid)return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const compact=n=>n?new Intl.NumberFormat('ko-KR',{notation:n>=1e6?'compact':'standard',maximumFractionDigits:1}).format(n)+'회':'시인성 선별';
  const displayName=p=>p.id==='s0101'?'숏템 기본형':p.name;
  grid.innerHTML=rows.map((p,i)=>`<button class="preset-card${i===0?' selected':''}" data-p20="${i}"><span class="check">✓</span><div class="thumb-pair"><img src="${esc(p.hook_image)}"><img src="${esc(p.body_image)}"></div><b>${esc(displayName(p))}</b><small>${compact(p.views)} · 훅+본문</small></button>`).join('');

  preview.classList.add('is-pristine');
  const base=document.createElement('img');base.className='precision-base';
  const layer=document.createElement('div');layer.className='precision-edit-layer';
  const badge=document.createElement('div');badge.className='precision-badge';badge.textContent='원본 실측 편집';layer.appendChild(badge);
  preview.append(base,layer);

  let current=0,kind='hook',sceneIndex=0;
  const fontScales=new Map();
  const dirtyFields=new Map();
  const captionPositions=new Map();
  const inputs=Object.fromEntries([...root.querySelectorAll('.layout-a [data-bind]')].map(x=>[x.dataset.bind,x]));
  const value=k=>inputs[k]?.value||' ';
  const rgba=hex=>hex&&/^#[0-9a-f]{6}$/i.test(hex)?hex:'#111111';
  const scaleKey=bind=>`${rows[current].id}:${kind}:${bind}`;
  const textScale=bind=>fontScales.get(scaleKey(bind))||1;
  const dirtyKey=()=>`${rows[current].id}:${kind}`;
  const captionKey=()=>`${rows[current].id}:body:${sceneIndex}:caption`;
  const captionOffset=()=>kind==='body'?(captionPositions.get(captionKey())||0)*6:0;
  const currentDirty=()=>dirtyFields.get(dirtyKey())||new Set();
  const markDirty=bind=>{
    const key=dirtyKey(),set=dirtyFields.get(key)||new Set();set.add(bind);dirtyFields.set(key,set);
  };

  root.querySelectorAll('.layout-a [data-field-key]').forEach(field=>{
    const count=field.querySelector('[data-count]');
    const stepper=document.createElement('span');
    stepper.className='font-stepper';
    stepper.innerHTML='<button type="button" data-font-step="-0.08" title="글자 작게">−</button><output>100%</output><button type="button" data-font-step="0.08" title="글자 크게">＋</button><button type="button" data-field-reset title="프리셋 기본값으로">↺</button>';
    count.before(stepper);
  });
  const captionField=root.querySelector('.layout-a [data-field-key="caption"]');
  if(captionField){
    const captionInput=captionField.querySelector('[data-bind="caption"]');
    captionInput.readOnly=true;captionInput.title='자막 문구는 대본에서 가져오며 여기서는 위치만 변경합니다.';captionInput.classList.add('caption-readonly');
    captionField.querySelector('.font-stepper').hidden=true;
    const captionCount=captionField.querySelector('[data-count]');if(captionCount)captionCount.hidden=true;
    const sceneLabel=document.createElement('span');sceneLabel.className='caption-scene-index';sceneLabel.dataset.captionSceneIndex='';captionField.querySelector('label').appendChild(sceneLabel);
    const controls=document.createElement('div');controls.className='caption-position';
    controls.innerHTML='<span>자막 위치</span><button type="button" data-caption-position="-1">↑ 위</button><button type="button" data-caption-position="0" class="active">가운데</button><button type="button" data-caption-position="1">↓ 아래</button>';
    const guide=document.createElement('p');guide.className='caption-guide';guide.textContent='대본의 줄바꿈 1개가 장면 1개로 자동 배치됩니다.';
    captionField.append(controls,guide);
  }
  const transport=root.querySelector('.layout-a .transport');
  const sceneStrip=root.querySelector('.layout-a .scene-strip');
  if(transport){
    transport.className='scene-navigator';
    transport.innerHTML='<button type="button" data-scene-step="-1" aria-label="이전 장면">‹ 이전</button><strong><span data-scene-current>1</span> / <span data-scene-total>12</span></strong><button type="button" data-scene-step="1" aria-label="다음 장면">다음 ›</button>';
  }
  if(sceneStrip){
    sceneStrip.className='scene-summary';
    sceneStrip.innerHTML='<span class="scene-dot"></span><b data-scene-name>1장 · 훅</b><small>줄바꿈 기준 자동 장면 분리</small>';
  }
  function sceneTotal(){return 12}
  function updateSceneUI(){
    root.querySelectorAll('.layout-a [data-scene-current]').forEach(el=>el.textContent=String(sceneIndex+1));
    root.querySelectorAll('.layout-a [data-scene-total]').forEach(el=>el.textContent=String(sceneTotal()));
    const name=root.querySelector('.layout-a [data-scene-name]');
    if(name)name.textContent=sceneIndex===0?'1장 · 훅':`${sceneIndex+1}장 · 본문`;
    root.querySelectorAll('.layout-a [data-caption-scene-index]').forEach(el=>el.textContent=`${sceneIndex+1}/${sceneTotal()}장`);
    root.querySelectorAll('.layout-a [data-scene-step]').forEach(button=>{
      const next=sceneIndex+Number(button.dataset.sceneStep);
      button.disabled=next<0||next>=sceneTotal();
    });
  }
  function updateSteppers(){
    root.querySelectorAll('.layout-a [data-field-key]').forEach(field=>{
      const output=field.querySelector('.font-stepper output');
      if(output)output.textContent=Math.round(textScale(field.dataset.fieldKey)*100)+'%';
    });
  }
  function updateCaptionButtons(){
    const position=captionPositions.get(captionKey())||0;
    root.querySelectorAll('.layout-a [data-caption-position]').forEach(button=>button.classList.toggle('active',Number(button.dataset.captionPosition)===position));
  }
  function presetValue(bind){
    const p=rows[current];
    return bind==='channel'?p.name:p.sample[bind];
  }
  function updateCount(input){
    const counter=input.closest('.field')?.querySelector('[data-count]');
    if(counter)counter.textContent=`${[...input.value].length}/${input.dataset.max}`;
  }
  function resetField(bind){
    const input=inputs[bind];if(!input)return;
    input.value=presetValue(bind)||'';fontScales.delete(scaleKey(bind));
    if(bind==='caption')captionPositions.delete(captionKey());
    markDirty(bind);updateCount(input);updateSteppers();updateCaptionButtons();renderEdit();
  }

  function frameKeys(frameKind,p){
    const frame=p[frameKind];
    const hasChannel=!!(frame?.channel_box||frame?.channel_boxes?.length||frame?.top_band);
    const lineCount=frame?.lines?.length||0;
    return p.id==='s0101'
      ? (frameKind==='hook'?['channel','hook1','hook2']:['channel','bodyTitle','caption'])
      : frameKind==='hook'
        ? [...(hasChannel?['channel']:[]),...(lineCount?['hook1']:[]),...(lineCount>1?['hook2']:[]),...(lineCount>2||frame?.white_box?.text?['bodyTitle']:[])]
        : [...(hasChannel?['channel']:[]),...(lineCount?['bodyTitle']:[]),...(lineCount>1||frame?.white_box?.text?['caption']:[])];
  }
  function fieldSet(frameKind,p){
    const keys=frameKeys(frameKind,p);
    root.querySelectorAll('.layout-a [data-field-key]').forEach(f=>f.hidden=!keys.includes(f.dataset.fieldKey));
    root.querySelectorAll('.layout-a [data-hook-label][data-body-label]').forEach(label=>label.textContent=label.dataset[frameKind+'Label']);
  }
  function addPatch(y,h,color,x=0,w=100,bind=''){
    const el=document.createElement('div');el.className='precision-patch';
    if(bind)el.dataset.editBind=bind;
    Object.assign(el.style,{left:x+'%',top:y+'%',width:w+'%',height:h+'%',background:rgba(color)});layer.insertBefore(el,badge);return el;
  }
  function fitText(el,startSize,minRatio=.58,checkHeight=false){
    const min=Math.max(5,startSize*minRatio);
    el.style.fontSize=startSize+'px';
    requestAnimationFrame(()=>{
      let size=startSize;
      while(size>min&&(el.scrollWidth>el.clientWidth+1||(checkHeight&&el.scrollHeight>el.clientHeight+1))){
        size-=.5;el.style.fontSize=size+'px';
      }
    });
  }
  function fitShortemText(){
    if(rows[current].id!=='s0101')return;
    const targets={channel:'[data-preview-channel]',hook1:'[data-preview-hook-1]',hook2:'[data-preview-hook-2]',bodyTitle:'[data-preview-body-title]',caption:'[data-preview-caption]'};
    Object.entries(targets).forEach(([bind,selector])=>root.querySelectorAll('.layout-a '+selector).forEach(el=>{
      el.style.fontSize='';const baseSize=parseFloat(getComputedStyle(el).fontSize)||18;
      fitText(el,baseSize*textScale(bind),.3);
    }));
  }
  function addText(text,ln,frame,color,role='center',bind='bodyTitle'){
    const scale=preview.clientHeight/frame.height;
    const pad=Math.max(2,Math.round(4*scale));
    const el=document.createElement('div');el.className='precision-text '+role;el.dataset.editBind=bind;
    const measuredBounds=role.includes('left')||role.includes('precision-channel');
    const left=measuredBounds?Math.max(0,ln.x0/frame.width*100-1.6):1;
    const right=measuredBounds?Math.max(0,(frame.width-1-ln.x1)/frame.width*100-1.6):1;
    const fontPx=ln.font_size?ln.font_size*scale:ln.h*scale*1.05;
    const stroke=Number(ln.stroke||0)*scale,shadowY=Number(ln.shadow_y||0)*scale;
    const family=ln.font_family||frame.font_family||'TmonMonsori';
    const weight=ln.font_weight||frame.font_weight||400;
    const letterPx=ln.letter_spacing!=null?ln.letter_spacing*scale:Math.max(-1.5,-.035*fontPx);
    const scaledFont=Math.max(9,fontPx*textScale(bind));
    const topOffset=bind==='caption'?captionOffset():0;
    Object.assign(el.style,{left:left+'%',right:right+'%',top:Math.max(0,ln.y0/frame.height*100-0.35+topOffset)+'%',height:(ln.h/frame.height*100+0.9)+'%',fontSize:scaledFont+'px',fontFamily:`"${family}",sans-serif`,fontWeight:String(weight),letterSpacing:letterPx+'px',color:rgba(color||ln.color||'#fff'),textShadow:shadowY?`0 ${shadowY}px 1px rgba(0,0,0,.88)`:'none',webkitTextStroke:stroke?`${stroke}px #080808`:'0',padding:`0 ${pad}px`,whiteSpace:ln.max_lines>1?'normal':'nowrap',lineHeight:ln.max_lines>1?'1.18':'1'});
    if(ln.accent_words){
      const words=String(text||' ').split(/\s+/),accent=document.createElement('span'),rest=document.createElement('span');
      accent.textContent=words.slice(0,ln.accent_words).join(' ');accent.style.color=ln.accent;accent.style.marginRight=Math.max(2,fontPx*.11)+'px';
      rest.textContent=words.slice(ln.accent_words).join(' ');el.append(accent,rest);
    }else el.textContent=text||' ';
    layer.insertBefore(el,badge);
  }
  function renderEdit(){
    [...layer.children].filter(x=>x!==badge).forEach(x=>x.remove());
    const p=rows[current],frame=p[kind];if(!frame)return;
    const dirty=currentDirty();
    const bg=frame.title_bg||frame.top_band?.color||'#111111';
    const channelBoxes=frame.channel_boxes?.length?frame.channel_boxes:(frame.channel_box?[frame.channel_box]:[]);
    if(dirty.has('channel')&&channelBoxes.length){
      channelBoxes.forEach(c=>{
      const scale=preview.clientHeight/frame.height,family=c.font_family||frame.font_family||'TmonMonsori';
      const canvas=renderEdit.canvas||(renderEdit.canvas=document.createElement('canvas'));
      const context=canvas.getContext('2d');context.font=`${c.font_weight||frame.font_weight||400} ${(c.font_size||c.height)*scale}px "${family}"`;
      const measuredWidth=(context.measureText(value('channel')).width+18*scale)/scale;
      const expandedWidth=Math.min(frame.width*.9,Math.max(c.width,measuredWidth));
      const center=c.x+c.width/2,expandedX=Math.max(frame.width*.02,Math.min(frame.width*.98-expandedWidth,center-expandedWidth/2));
      const box=addPatch(c.y/frame.height*100,c.height/frame.height*100,c.background,expandedX/frame.width*100,expandedWidth/frame.width*100,'channel');
      box.style.borderRadius=((Number(c.radius)||0)*preview.clientHeight/frame.height)+'px';if(c.border)box.style.border=`${Math.max(1,preview.clientHeight/frame.height)}px solid ${c.border}`;
      const channelLine={x0:expandedX,x1:expandedX+expandedWidth,y0:c.y,y1:c.y+c.height,h:c.height,font_size:c.font_size,font_family:c.font_family,font_weight:c.font_weight,letter_spacing:c.letter_spacing,stroke:0,shadow_y:0};
      addText(value('channel'),channelLine,frame,c.color,'center precision-channel','channel');
      });
    }else if(dirty.has('channel')&&frame.top_band){
      const t=frame.top_band, y=t.y0/frame.height*100, h=(t.y1-t.y0+1)/frame.height*100;
      addPatch(y,h,t.color,20,60,'channel');
      const channelLine={x0:Math.round(frame.width*.2),x1:Math.round(frame.width*.8),y0:t.y0,y1:t.y1,h:t.y1-t.y0+1};
      addText(value('channel'),channelLine,frame,'#FFFFFF','center precision-channel','channel');
    }
    const lines=frame.lines||[];
    lines.forEach((ln,i)=>{
      const key=kind==='hook'?(i===0?'hook1':i===1?'hook2':'bodyTitle'):(i===0?'bodyTitle':'caption');
      if(!dirty.has(key))return;
      const pt=ln.patch_top??2,pb=ln.patch_bottom??2;
      const offset=key==='caption'?captionOffset():0;
      if(!ln.skip_patch)addPatch(Math.max(0,(ln.y0-pt)/frame.height*100+offset),(ln.h+pt+pb)/frame.height*100,ln.background||bg,0,100,key);
      else addPatch(Math.max(0,(ln.y0-pt)/frame.height*100+offset),(ln.h+pt+pb)/frame.height*100,ln.background||frame.boxes?.[0]?.background||bg,Math.max(0,ln.x0/frame.width*100-2),(ln.x1-ln.x0)/frame.width*100+4,key);
      const align=(ln.lpct??50)<4&&(ln.rpct??50)>10?'left':'center';
      addText(value(key),ln,frame,ln.color,align,key);
    });
    const wb=frame.white_box;
    if(wb?.text){
      const key=kind==='hook'?'bodyTitle':'caption';
      if(dirty.has(key)){const offset=key==='caption'?captionOffset():0;addPatch(wb.y0/frame.height*100+offset,(wb.y1-wb.y0+1)/frame.height*100,'#FFFFFF',0,100,key);addText(value(key),wb.text,frame,'#111111','center',key);}
    }
  }
  function showFrame(next){
    kind=next;
    if(kind==='hook')sceneIndex=0;
    else if(sceneIndex===0)sceneIndex=1;
    const p=rows[current],source=kind==='hook'?p.hook_image:p.body_image;
    base.src=source;
    preview.classList.toggle('is-body',kind==='body');
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();
  }
  function showScene(nextIndex){
    sceneIndex=Math.max(0,Math.min(sceneTotal()-1,nextIndex));
    kind=sceneIndex===0?'hook':'body';
    const p=rows[current],source=kind==='hook'?p.hook_image:p.body_image;
    base.src=source;preview.classList.toggle('is-body',kind==='body');
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();
  }
  function selectPreset(index){
    current=index;const p=rows[index];
    sceneIndex=kind==='hook'?0:Math.max(1,sceneIndex);
    preview.classList.remove('template-shortem');
    preview.classList.add('template-precision');
    base.hidden=false;layer.hidden=false;
    dirtyFields.set(`${p.id}:hook`,new Set(frameKeys('hook',p)));
    dirtyFields.set(`${p.id}:body`,new Set(frameKeys('body',p)));
    grid.querySelectorAll('[data-p20]').forEach((x,i)=>x.classList.toggle('selected',i===index));
    inputs.channel.value=p.name;inputs.hook1.value=p.sample.hook1;inputs.hook2.value=p.sample.hook2;inputs.bodyTitle.value=p.sample.bodyTitle;inputs.caption.value=p.sample.caption;
    root.querySelectorAll('[data-preview-channel]').forEach(x=>x.textContent=p.name);
    root.querySelectorAll('[data-preview-hook-1]').forEach(x=>x.textContent=p.sample.hook1);
    root.querySelectorAll('[data-preview-hook-2]').forEach(x=>x.textContent=p.sample.hook2);
    root.querySelectorAll('[data-preview-body-title]').forEach(x=>x.textContent=p.sample.bodyTitle);
    root.querySelectorAll('[data-preview-caption]').forEach(x=>x.textContent=p.sample.caption);
    Object.values(inputs).forEach(updateCount);
    root.querySelector('[data-stage-name]').textContent=displayName(p);
    const accent=p.hook?.lines?.[1]?.color||p.hook?.lines?.[0]?.color||'#ffe500';
    const top=p.hook?.top_band?.color||p.hook?.title_bg||'#111111';
    root.querySelector('[data-accent-swatch]').style.background=accent;root.querySelector('[data-top-swatch]').style.background=top;
    preview.classList.remove('is-pristine');showFrame(kind);
  }
  grid.addEventListener('click',e=>{const card=e.target.closest('[data-p20]');if(card)selectPreset(+card.dataset.p20)});
  root.querySelectorAll('.layout-a [data-frame]').forEach(button=>button.addEventListener('click',()=>showFrame(button.dataset.frame)));
  root.querySelector('.layout-a .scene-navigator')?.addEventListener('click',event=>{
    const button=event.target.closest('[data-scene-step]');if(!button)return;
    showScene(sceneIndex+Number(button.dataset.sceneStep));
  });
  Object.values(inputs).forEach(input=>input.addEventListener('input',()=>{
    markDirty(input.dataset.bind);preview.classList.remove('is-pristine');renderEdit();
  }));
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-font-step]');if(!button)return;
    const bind=button.closest('[data-field-key]').dataset.fieldKey;
    const next=Math.min(1.6,Math.max(.55,textScale(bind)+Number(button.dataset.fontStep)));
    fontScales.set(scaleKey(bind),next);markDirty(bind);preview.classList.remove('is-pristine');updateSteppers();renderEdit();
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-field-reset]');if(!button)return;
    resetField(button.closest('[data-field-key]').dataset.fieldKey);
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-caption-position]');if(!button)return;
    captionPositions.set(captionKey(),Number(button.dataset.captionPosition));markDirty('caption');updateCaptionButtons();renderEdit();
  });
  addEventListener('resize',()=>{if(!preview.classList.contains('is-pristine'))renderEdit()});
  selectPreset(0);
})();
