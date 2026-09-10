(()=>{
  const storyRows=window.PRECISION20||[],fixedRows=window.CONTINUOUS20||[];
  let rows=storyRows,mode='story';
  const root=document;
  const preview=root.getElementById('a-live-preview');
  const grid=root.querySelector('.layout-a .preset-grid');
  if(!rows.length||!preview||!grid)return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const compact=n=>n?new Intl.NumberFormat('ko-KR',{notation:n>=1e6?'compact':'standard',maximumFractionDigits:1}).format(n)+'회':'시인성 선별';
  const displayName=p=>p.id==='s0101'?'숏템 기본형':p.name;
  const renderGrid=()=>{
    grid.innerHTML=rows.map((p,i)=>mode==='continuous'
      ? `<button class="preset-card fixed-card${i===0?' selected':''}" data-p20="${i}"><span class="check">✓</span><div class="fixed-thumb" style="--fixed-bg:${p.thumb.bg};--fixed-c1:${p.thumb.c1};--fixed-c2:${p.thumb.c2};background-image:url('${esc(p.thumbnail_image)}')"><i>숏템메이커</i><strong>처음부터 끝까지</strong><em>같은 디자인 유지</em></div><b>${esc(p.name)}</b><small>1장~끝까지 동일</small></button>`
      : `<button class="preset-card${i===0?' selected':''}" data-p20="${i}"><span class="check">✓</span><div class="thumb-pair"><img src="${esc(p.hook_image)}"><img src="${esc(p.body_image)}"></div><b>${esc(displayName(p))}</b><small>${compact(p.views)} · 훅+본문</small></button>`).join('');
  };
  const presetPane=grid.closest('.pane'),modeBar=document.createElement('div');modeBar.className='template-mode-bar';
  modeBar.innerHTML='<button type="button" data-template-mode="story" class="active">썰쇼핑형 <small>20</small></button><button type="button" data-template-mode="continuous">전장면 고정형 <small>20</small></button>';
  presetPane.querySelector('.pane-head').after(modeBar);renderGrid();

  preview.classList.add('is-pristine');
  const base=document.createElement('img');base.className='precision-base';
  const layer=document.createElement('div');layer.className='precision-edit-layer';
  const badge=document.createElement('div');badge.className='precision-badge';badge.textContent='원본 실측 편집';layer.appendChild(badge);
  preview.append(base,layer);

  let current=0,kind='hook',sceneIndex=0;
  const fontScales=new Map();
  const fittedText=new Map();
  const textOffsets=new Map();
  const colorOverrides=new Map();
  const dirtyFields=new Map();
  const captionPositions=new Map();
  const inputs=Object.fromEntries([...root.querySelectorAll('.layout-a [data-bind]')].map(x=>[x.dataset.bind,x]));
  const value=k=>inputs[k]?.value||' ';
  const rgba=hex=>hex&&/^#[0-9a-f]{6}$/i.test(hex)?hex:'#111111';
  const frameFor=(p,index=sceneIndex)=>p.mode==='continuous'?p.frame:p[index===0?'hook':'body'];
  const imageFor=(p,index=sceneIndex)=>p.mode==='continuous'?p.frame_image:(index===0?p.hook_image:p.body_image);
  const frameKind=()=>mode==='continuous'?'frame':kind;
  const scaleKey=bind=>`${rows[current].id}:${frameKind()}:${bind}`;
  const textScale=bind=>fontScales.get(scaleKey(bind))||1;
  const textOffset=bind=>textOffsets.get(scaleKey(bind))||0;
  const colorKey=role=>`${rows[current].id}:${frameKind()}:${role}`;
  const colorFor=(role,fallback)=>colorOverrides.get(colorKey(role))||fallback;
  const dirtyKey=()=>`${rows[current].id}:${frameKind()}`;
  const captionKey=()=>`${rows[current].id}:${mode}:${sceneIndex}:caption`;
  const captionOffset=()=>(kind==='body'||mode==='continuous')?(captionPositions.get(captionKey())||0)*6:0;
  const currentDirty=()=>dirtyFields.get(dirtyKey())||new Set();
  const markDirty=bind=>{
    const key=dirtyKey(),set=dirtyFields.get(key)||new Set();set.add(bind);dirtyFields.set(key,set);
  };

  root.querySelectorAll('.layout-a [data-field-key]').forEach(field=>{
    const count=field.querySelector('[data-count]');
    const stepper=document.createElement('span');
    stepper.className='font-stepper';
    stepper.innerHTML='<button type="button" data-font-step="-0.08" title="글자 작게">−</button><output>100%</output><button type="button" data-font-step="0.08" title="글자 크게">＋</button><button type="button" data-position-step="-1" title="위로">↑</button><button type="button" data-position-step="1" title="아래로">↓</button><button type="button" data-field-reset title="프리셋 기본값으로">↺</button>';
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
  const colorRow=root.querySelector('.layout-a .color-row');
  if(colorRow)colorRow.innerHTML='<label class="swatch"> <input type="color" data-color-role="white" value="#ffffff"><span>흰색</span></label><label class="swatch"><input type="color" data-color-role="accent" value="#ffe600"><span>강조</span></label><label class="swatch"><input type="color" data-color-role="background" value="#211f19"><span>배경</span></label>';
  function sceneTotal(){return 12}
  function updateSceneUI(){
    root.querySelectorAll('.layout-a [data-scene-current]').forEach(el=>el.textContent=String(sceneIndex+1));
    root.querySelectorAll('.layout-a [data-scene-total]').forEach(el=>el.textContent=String(sceneTotal()));
    const name=root.querySelector('.layout-a [data-scene-name]');
    if(name)name.textContent=mode==='continuous'?`${sceneIndex+1}장 · 동일 디자인`:(sceneIndex===0?'1장 · 훅':`${sceneIndex+1}장 · 본문`);
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
    return bind==='channel'?(p.sample.channel||'숏템메이커'):p.sample[bind];
  }
  function updateCount(input){
    const counter=input.closest('.field')?.querySelector('[data-count]');
    if(counter)counter.textContent=`${[...input.value].length}/${input.dataset.max}`;
  }
  function resetField(bind){
    const input=inputs[bind];if(!input)return;
    input.value=presetValue(bind)||'';fontScales.delete(scaleKey(bind));textOffsets.delete(scaleKey(bind));
    [...fittedText.keys()].filter(key=>key.startsWith(scaleKey(bind)+':')).forEach(key=>fittedText.delete(key));
    if(bind==='caption')captionPositions.delete(captionKey());
    markDirty(bind);updateCount(input);updateSteppers();updateCaptionButtons();renderEdit();
  }

  function frameKeys(frameKind,p){
    if(p.mode==='continuous')return [...(p.frame.channel_boxes?.length?['channel']:[]),...new Set((p.frame.lines||[]).map(line=>line.bind).filter(Boolean))];
    const frame=p[frameKind];
    const hasChannel=!!(frame?.channel_box||frame?.channel_boxes?.length);
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
    const label1=root.querySelector('.layout-a [data-field-key="hook1"] [data-field-label]');
    const label2=root.querySelector('.layout-a [data-field-key="hook2"] [data-field-label]');
    if(label1)label1.textContent=mode==='continuous'?'제목 1':'훅 제목 1';
    if(label2)label2.textContent=mode==='continuous'?'제목 2':'훅 제목 2';
  }
  function addPatch(y,h,color,x=0,w=100,bind=''){
    const el=document.createElement('div');el.className='precision-patch';
    if(bind)el.dataset.editBind=bind;
    const paint=bind&&bind!=='channel'?colorFor('background',color):color;
    Object.assign(el.style,{left:x+'%',top:y+'%',width:w+'%',height:h+'%',background:rgba(paint)});layer.insertBefore(el,badge);return el;
  }
  function fitText(el,startSize,minRatio=.58,checkHeight=false){
    const min=Math.max(5,startSize*minRatio);
    el.style.fontSize=startSize+'px';
    let size=startSize;
    while(size>min&&(el.scrollWidth>el.clientWidth+2||(checkHeight&&el.scrollHeight>el.clientHeight+4))){
      size-=.5;el.style.fontSize=size+'px';
    }
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
    const measuredBounds=role.includes('left')||role.includes('precision-channel');
    const pad=measuredBounds?Math.max(2,Math.round(4*scale)):0;
    const el=document.createElement('div');el.className='precision-text '+role;el.dataset.editBind=bind;
    const left=measuredBounds?Math.max(0,ln.x0/frame.width*100-1.6):0;
    const right=measuredBounds?Math.max(0,(frame.width-1-ln.x1)/frame.width*100-1.6):0;
    const fontPx=ln.font_size?ln.font_size*scale:ln.h*scale*1.05;
    const stroke=Number(ln.stroke||0)*scale,shadowY=Number(ln.shadow_y||0)*scale;
    const family=ln.font_family||frame.font_family||'TmonMonsori';
    const weight=ln.font_weight||frame.font_weight||400;
    const letterPx=ln.letter_spacing!=null?ln.letter_spacing*scale:Math.max(-1.5,-.035*fontPx);
    const scaledFont=Math.max(9,fontPx*textScale(bind));
    const topOffset=(bind==='caption'?captionOffset():0)+textOffset(bind);
    const verticalNudge=bind==='channel'?.7:-.35;
    Object.assign(el.style,{left:left+'%',right:right+'%',top:Math.max(0,ln.y0/frame.height*100+verticalNudge+topOffset)+'%',height:(ln.h/frame.height*100+0.9)+'%',fontSize:scaledFont+'px',fontFamily:`"${family}",sans-serif`,fontWeight:String(weight),letterSpacing:letterPx+'px',color:rgba(color||ln.color||'#fff'),textShadow:shadowY?`0 ${shadowY}px 1px rgba(0,0,0,.88)`:'none',webkitTextStroke:stroke?`${stroke}px #080808`:'0',padding:`0 ${pad}px`,whiteSpace:ln.max_lines>1?'normal':'nowrap',lineHeight:ln.max_lines>1?'1.18':'1'});
    if(ln.accent_words){
      const words=String(text||' ').split(/\s+/),accent=document.createElement('span'),rest=document.createElement('span');
      accent.textContent=words.slice(0,ln.accent_words).join(' ');accent.style.color=ln.accent;accent.style.marginRight=Math.max(2,fontPx*.11)+'px';
      rest.textContent=words.slice(ln.accent_words).join(' ');el.append(accent,rest);
    }else el.textContent=text||' ';
    layer.insertBefore(el,badge);
    const fitKey=`${scaleKey(bind)}:${ln.x0}:${ln.y0}`,chars=Math.max(1,[...String(text||' ')].length),cached=fittedText.get(fitKey);
    if(cached&&chars<=cached.capacity){el.style.fontSize=cached.size+'px';if(cached.letter!=null)el.style.letterSpacing=cached.letter+'px';if(cached.xscale<1){el.style.transform=`scaleX(${cached.xscale})`;el.style.transformOrigin=role.includes('left')?'left center':'center';}}
    else {fitText(el,scaledFont,.12,true);const fitted=parseFloat(el.style.fontSize)||scaledFont;let reserved=Math.max(4,fitted*chars/(chars+1));el.style.fontSize=reserved+'px';if(el.scrollWidth>el.clientWidth+2){reserved=Math.max(4,reserved*(el.clientWidth/Math.max(1,el.scrollWidth))*.96);el.style.fontSize=reserved+'px';}let fittedLetter=parseFloat(getComputedStyle(el).letterSpacing)||0;while(el.scrollWidth>el.clientWidth+2&&fittedLetter>-reserved*.3){fittedLetter-=.25;el.style.letterSpacing=fittedLetter+'px';}const xscale=Math.min(1,el.clientWidth/Math.max(1,el.scrollWidth)*.98);if(xscale<1){el.style.transform=`scaleX(${xscale})`;el.style.transformOrigin=role.includes('left')?'left center':'center';}fittedText.set(fitKey,{capacity:chars+1,size:reserved,letter:fittedLetter,xscale});}
    return el;
  }
  function renderEdit(){
    [...layer.children].filter(x=>x!==badge).forEach(x=>x.remove());
    const p=rows[current],frame=frameFor(p);if(!frame)return;
    const dirty=currentDirty();
    const bg=frame.title_bg||frame.top_band?.color||'#111111';
    if(mode==='continuous'){
      (frame.fixed_bands||[]).forEach(b=>addPatch(b.y0/frame.height*100,(b.y1-b.y0)/frame.height*100,b.color));
      (frame.boxes||[]).forEach(b=>{const box=addPatch(b.y/frame.height*100,b.height/frame.height*100,b.background,b.x/frame.width*100,b.width/frame.width*100);if(b.border)box.style.border=`${b.border_width||1}px solid ${b.border}`;});
    }
    const channelBoxes=frame.channel_boxes?.length?frame.channel_boxes:(frame.channel_box?[frame.channel_box]:[]);
    if(dirty.has('channel')&&channelBoxes.length){
      channelBoxes.forEach(c=>{
      const scale=preview.clientHeight/frame.height,maxWidth=frame.width*.9,maxX=frame.width*.05;
      const box=addPatch(c.y/frame.height*100,c.height/frame.height*100,c.background,c.x/frame.width*100,c.width/frame.width*100,'channel');
      box.style.borderRadius=((Number(c.radius)||0)*preview.clientHeight/frame.height)+'px';if(c.border)box.style.border=`${Math.max(1,preview.clientHeight/frame.height)}px solid ${c.border}`;
      const channelLine={x0:maxX,x1:maxX+maxWidth,y0:c.y,y1:c.y+c.height,h:c.height,font_size:c.font_size,font_family:c.font_family,font_weight:c.font_weight,letter_spacing:c.letter_spacing,stroke:0,shadow_y:0};
      const channelText=addText(value('channel'),channelLine,frame,c.color,'center precision-channel','channel');
      const range=document.createRange();range.selectNodeContents(channelText);
      const contentWidth=range.getBoundingClientRect().width/scale+18;
      const expandedWidth=Math.min(maxWidth,Math.max(c.width,contentWidth));
      const center=c.x+c.width/2,expandedX=Math.max(frame.width*.02,Math.min(frame.width*.98-expandedWidth,center-expandedWidth/2));
      Object.assign(box.style,{left:expandedX/frame.width*100+'%',width:expandedWidth/frame.width*100+'%'});
      Object.assign(channelText.style,{left:expandedX/frame.width*100+'%',right:(frame.width-expandedX-expandedWidth)/frame.width*100+'%'});
      });
    }
    const lines=frame.lines||[];
    lines.forEach((ln,i)=>{
      const key=ln.bind||(kind==='hook'?(i===0?'hook1':i===1?'hook2':'bodyTitle'):(i===0?'bodyTitle':'caption'));
      if(!dirty.has(key))return;
      const pt=ln.patch_top??2,pb=ln.patch_bottom??2;
      const offset=(key==='caption'?captionOffset():0)+textOffset(key);
      if(!ln.no_patch){
        if(offset)addPatch(Math.max(0,(ln.y0-pt)/frame.height*100),(ln.h+pt+pb)/frame.height*100,ln.background||bg,0,100,key);
        if(!ln.skip_patch)addPatch(Math.max(0,(ln.y0-pt)/frame.height*100+offset),(ln.h+pt+pb)/frame.height*100,ln.background||bg,0,100,key);
        else addPatch(Math.max(0,(ln.y0-pt)/frame.height*100+offset),(ln.h+pt+pb)/frame.height*100,ln.background||frame.boxes?.[0]?.background||bg,Math.max(0,ln.x0/frame.width*100-2),(ln.x1-ln.x0)/frame.width*100+4,key);
      }
      const align=(ln.lpct??50)<4&&(ln.rpct??50)>10?'left':'center';
      const roleColor=key==='hook2'?'accent':key==='hook1'?'white':null;
      addText(value(key),ln,frame,roleColor?colorFor(roleColor,ln.color):ln.color,align,key);
    });
    const wb=frame.white_box;
    if(wb?.text){
      const key=kind==='hook'?'bodyTitle':'caption';
      if(dirty.has(key)){const offset=(key==='caption'?captionOffset():0)+textOffset(key);if(offset)addPatch(wb.y0/frame.height*100,(wb.y1-wb.y0+1)/frame.height*100,'#FFFFFF',0,100,key);addPatch(wb.y0/frame.height*100+offset,(wb.y1-wb.y0+1)/frame.height*100,'#FFFFFF',0,100,key);addText(value(key),wb.text,frame,'#111111','center',key);}
    }
  }
  function showFrame(next){
    kind=mode==='continuous'?'hook':next;
    if(mode!=='continuous'&&kind==='hook')sceneIndex=0;
    else if(mode!=='continuous'&&sceneIndex===0)sceneIndex=1;
    const p=rows[current],source=imageFor(p);
    base.src=source;
    preview.classList.toggle('is-body',mode!=='continuous'&&kind==='body');
    preview.classList.toggle('is-continuous',mode==='continuous');
    const seg=root.querySelector('.layout-a .seg');if(seg)seg.hidden=mode==='continuous';
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();
  }
  function showScene(nextIndex){
    sceneIndex=Math.max(0,Math.min(sceneTotal()-1,nextIndex));
    kind=mode==='continuous'?'hook':sceneIndex===0?'hook':'body';
    const p=rows[current],source=imageFor(p,sceneIndex);
    base.src=source;preview.classList.toggle('is-body',mode!=='continuous'&&kind==='body');
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();
  }
  function selectPreset(index){
    current=index;const p=rows[index];
    if(mode==='continuous')kind='hook';else sceneIndex=kind==='hook'?0:Math.max(1,sceneIndex);
    preview.classList.remove('template-shortem');
    preview.classList.add('template-precision');
    base.hidden=false;layer.hidden=false;
    if(mode==='continuous')dirtyFields.set(`${p.id}:frame`,new Set(frameKeys('frame',p)));
    else {dirtyFields.set(`${p.id}:hook`,new Set(frameKeys('hook',p)));dirtyFields.set(`${p.id}:body`,new Set(frameKeys('body',p)));}
    grid.querySelectorAll('[data-p20]').forEach((x,i)=>x.classList.toggle('selected',i===index));
    inputs.channel.value=p.sample.channel||'숏템메이커';inputs.hook1.value=p.sample.hook1;inputs.hook2.value=p.sample.hook2;inputs.bodyTitle.value=p.sample.bodyTitle;inputs.caption.value=p.sample.caption;
    root.querySelectorAll('[data-preview-channel]').forEach(x=>x.textContent=inputs.channel.value);
    root.querySelectorAll('[data-preview-hook-1]').forEach(x=>x.textContent=p.sample.hook1);
    root.querySelectorAll('[data-preview-hook-2]').forEach(x=>x.textContent=p.sample.hook2);
    root.querySelectorAll('[data-preview-body-title]').forEach(x=>x.textContent=p.sample.bodyTitle);
    root.querySelectorAll('[data-preview-caption]').forEach(x=>x.textContent=p.sample.caption);
    Object.values(inputs).forEach(updateCount);
    root.querySelector('[data-stage-name]').textContent=displayName(p);
    const frame=frameFor(p),accent=frame?.lines?.[1]?.color||frame?.lines?.[0]?.color||'#ffe500';
    const top=frame?.top_band?.color||frame?.title_bg||'#111111';
    const accentInput=colorRow?.querySelector('[data-color-role="accent"]'),topInput=colorRow?.querySelector('[data-color-role="background"]');
    if(accentInput)accentInput.value=accent;if(topInput)topInput.value=top;
    preview.classList.remove('is-pristine');showFrame(kind);
  }
  grid.addEventListener('click',e=>{const card=e.target.closest('[data-p20]');if(card)selectPreset(+card.dataset.p20)});
  modeBar.addEventListener('click',event=>{
    const button=event.target.closest('[data-template-mode]');if(!button)return;
    mode=button.dataset.templateMode;rows=mode==='continuous'?fixedRows:storyRows;if(!rows.length)return;
    modeBar.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===button));current=0;kind='hook';sceneIndex=0;renderGrid();selectPreset(0);
  });
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
    const next=Math.min(2,Math.max(.55,textScale(bind)+Number(button.dataset.fontStep)));
    fontScales.set(scaleKey(bind),next);[...fittedText.keys()].filter(key=>key.startsWith(scaleKey(bind)+':')).forEach(key=>fittedText.delete(key));markDirty(bind);preview.classList.remove('is-pristine');updateSteppers();renderEdit();
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-position-step]');if(!button)return;
    const bind=button.closest('[data-field-key]').dataset.fieldKey;
    textOffsets.set(scaleKey(bind),Math.max(-18,Math.min(18,textOffset(bind)+Number(button.dataset.positionStep)*.5)));
    markDirty(bind);preview.classList.remove('is-pristine');renderEdit();
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-field-reset]');if(!button)return;
    resetField(button.closest('[data-field-key]').dataset.fieldKey);
  });
  colorRow?.addEventListener('input',event=>{
    const input=event.target.closest('[data-color-role]');if(!input)return;
    colorOverrides.set(colorKey(input.dataset.colorRole),input.value);preview.classList.remove('is-pristine');renderEdit();
  });
  const saveButton=root.querySelector('.layout-a .secondary');
  saveButton?.addEventListener('click',()=>{
    const p=rows[current],snapshot={mode,presetId:p.id,frameKind:frameKind(),text:Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value])),fontScales:Object.fromEntries(fontScales),textOffsets:Object.fromEntries(textOffsets),colors:Object.fromEntries(colorOverrides)};
    localStorage.setItem('scene_style_preset',JSON.stringify(snapshot));saveButton.textContent='✓ 현재 설정 저장됨';setTimeout(()=>saveButton.textContent='현재 설정 저장',1400);
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-caption-position]');if(!button)return;
    captionPositions.set(captionKey(),Number(button.dataset.captionPosition));markDirty('caption');updateCaptionButtons();renderEdit();
  });
  addEventListener('resize',()=>{if(!preview.classList.contains('is-pristine'))renderEdit()});
  document.fonts?.ready?.then(()=>{fittedText.clear();renderEdit()});
  saveButton&&(saveButton.textContent='현재 설정 저장');
  if(new URLSearchParams(location.search).get('mode')==='continuous')modeBar.querySelector('[data-template-mode="continuous"]').click();else selectPreset(0);
})();
