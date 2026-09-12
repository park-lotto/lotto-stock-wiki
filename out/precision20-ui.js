(()=>{
  const storyRows=window.PRECISION20||[],fixedRows=window.CONTINUOUS20||[];
  let rows=storyRows,mode='story';
  const root=document;
  const qaMode=new URLSearchParams(location.search).has('qa');
  const preview=root.getElementById('a-live-preview');
  const grid=root.querySelector('.layout-a .preset-grid');
  if(!rows.length||!preview||!grid)return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const compact=n=>n?new Intl.NumberFormat('ko-KR',{notation:n>=1e6?'compact':'standard',maximumFractionDigits:1}).format(n)+'회':'시인성 선별';
  const displayName=p=>p.id==='s0101'?'숏템 기본형':p.name;
  const fontNames={SBAggroB:'강렬한 어그로체',YgJalnan:'친근한 잘난체',Cafe24Ohsquare:'각진 카페24',BinggraeBold:'부드러운 빙그레',Jalnan2:'잘난체 2',JalnanGothic:'잘난고딕',GasoekOne:'묵직한 가석체',GmarketSansBold:'지마켓 산스',TmonMonsori:'티몬 몬소리',BlackHanSans:'검은고딕',GothicA1Black:'고딕 A1',Pretendard:'깔끔한 프리텐다드'};
  const fontLabel=p=>{const family=(p.hook||p.frame)?.lines?.[0]?.font_family;return fontNames[family==='PretendardXBold'?'Pretendard':family]||'템플릿 전용 서체'};
  const uniformMedia='assets/scene-style/uniform-household-demo.png';
  const fixedLayouts=new Map(),fixedColors=new Map();
  const fixedBaseLayout=frame=>{
    const footer=(frame?.cleanup_regions||[]).find(region=>region.role==='source-footer');
    return {top:Math.round((frame?.video_from?.y||0)/(frame?.height||1)*100),bottom:footer&&frame?.lines?.some(l=>l.bind==='caption')?Math.min(14,Math.round(footer.height/frame.height*100)):0};
  };
  const fixedLayoutFor=(presetId,frame)=>fixedLayouts.get(presetId)||fixedBaseLayout(frame);
  const fixedBaseColors=frame=>{
    const titleLines=(frame?.lines||[]).filter(line=>line.bind!=='caption');
    const footer=(frame?.cleanup_regions||[]).find(region=>region.role==='source-footer');
    return {top:frame?.title_bg||frame?.top_band?.color||'#000000',bottom:footer?.background||'#000000',title1:titleLines[0]?.color||'#FFFFFF',title2:titleLines[1]?.color||titleLines[0]?.color||'#FFFFFF'};
  };
  const fixedColorsFor=(presetId,frame)=>({...fixedBaseColors(frame),...(fixedColors.get(presetId)||{})});
  const mediaBounds=(frame,presetId)=>{
    if(!frame)return {top:0,height:100};
    if(presetId?.startsWith('fixed_')){
      const layout=fixedLayoutFor(presetId,frame);
      return {top:layout.top,height:Math.max(25,100-layout.top-layout.bottom)};
    }
    const start=frame.video_from?.y||0;
    const footer=(frame.cleanup_regions||[]).find(region=>region.role==='source-footer');
    const end=footer?.y||frame.height;
    return {top:start/frame.height*100,height:Math.max(0,end-start)/frame.height*100};
  };
  const fixedThumb=p=>`assets/scene-style/thumbnails/fixed-${p.source_id}.png`;
  const storyThumb=(p,kind)=>`assets/scene-style/thumbnails/story-${p.id}-${kind}.png`;
  const storyHasCaptionSlot=frame=>frame?.caption_slot?frame.caption_slot.mode==='reserved':!!frame?.white_box||(frame?.cleanup_regions||[]).some(r=>r.role==='source-footer');
  const presetHasCaptionSlot=p=>p.mode==='continuous'?p.frame?.caption_slot?.mode==='reserved':storyHasCaptionSlot(p.body);
  const captionBadge=p=>presetHasCaptionSlot(p)?'<span class="caption-kind reserved">자막칸</span>':'<span class="caption-kind overlay">영상 위</span>';
  const renderGrid=()=>{
    const count=root.querySelector('.layout-a .pane-head .count');if(count)count.textContent=`${storyRows.length+fixedRows.length}개`;
    grid.innerHTML=rows.map((p,i)=>mode==='continuous'
      ? `<button class="preset-card fixed-card${i===0?' selected':''}" data-p20="${i}"><span class="check">✓</span>${captionBadge(p)}<div class="fixed-thumb" style="background-image:url('${fixedThumb(p)}')"></div><b>${esc(p.name)}</b><small>${esc(fontLabel(p))} · 고정형</small></button>`
      : `<button class="preset-card${i===0?' selected':''}" data-p20="${i}"><span class="check">✓</span>${captionBadge(p)}<div class="thumb-pair"><img src="${storyThumb(p,'hook')}"><img src="${storyThumb(p,'body')}"></div><b>${esc(displayName(p))}</b><small>${esc(fontLabel(p))} · 훅+본문</small></button>`).join('');
  };
  const presetPane=grid.closest('.pane'),modeBar=document.createElement('div');modeBar.className='template-mode-bar';
  modeBar.innerHTML='<button type="button" data-template-mode="story" class="active">썰쇼핑형 <small>20</small></button><button type="button" data-template-mode="continuous">전장면 고정형 <small>20</small></button>';
  presetPane.querySelector('.pane-head').after(modeBar);renderGrid();

  preview.classList.add('is-pristine');
  const base=document.createElement('img');base.className='precision-base';
  const media=document.createElement('img');media.className='precision-media';media.src=uniformMedia;media.alt='공통 생활용품 시연 장면';
  const layer=document.createElement('div');layer.className='precision-edit-layer';
  const badge=document.createElement('div');badge.className='precision-badge';badge.textContent='원본 실측 편집';layer.appendChild(badge);
  preview.append(base,media,layer);

  let current=0,kind='hook',sceneIndex=0,hookMotion='zoom-punch',hookMotionSpeed=.72;
  const fontScales=new Map();
  const fittedText=new Map();
  const textOffsets=new Map();
  const colorOverrides=new Map();
  const dirtyFields=new Map();
  const captionPositions=new Map();
  const captionTexts=new Map(),captionDrags=new Map();
  const inputs=Object.fromEntries([...root.querySelectorAll('.layout-a [data-bind]')].map(x=>[x.dataset.bind,x]));
  const value=k=>inputs[k]?.value||' ';
  const rgba=hex=>hex&&/^#[0-9a-f]{6}$/i.test(hex)?hex:'#111111';
  const frameFor=(p,index=sceneIndex)=>p.mode==='continuous'?p.frame:p[index===0?'hook':'body'];
  const imageFor=(p,index=sceneIndex)=>p.mode==='continuous'?p.frame_image:(index===0?p.hook_image:p.body_image);
  const frameKind=()=>mode==='continuous'?'frame':kind;
  const scaleKey=bind=>`${rows[current].id}:${frameKind()}:${bind}${bind==='caption'?':'+sceneIndex:''}`;
  const textScale=bind=>fontScales.get(scaleKey(bind))||1;
  const textOffset=bind=>textOffsets.get(scaleKey(bind))||0;
  const colorKey=role=>`${rows[current].id}:${frameKind()}:${role}`;
  const colorFor=(role,fallback)=>colorOverrides.get(colorKey(role))||fallback;
  const dirtyKey=()=>`${rows[current].id}:${frameKind()}`;
  const captionKey=()=>`${rows[current].id}:${mode}:${sceneIndex}:caption`;
  const currentHasCaptionSlot=()=>mode==='continuous'?frameFor(rows[current])?.caption_slot?.mode==='reserved':kind==='body'&&storyHasCaptionSlot(frameFor(rows[current]));
  const captionOffset=()=>(captionDrags.get(captionKey())?.y||0)+(currentHasCaptionSlot()?0:(kind==='body'||mode==='continuous')?(captionPositions.get(captionKey())||0)*6:0);
  const captionX=()=>captionDrags.get(captionKey())?.x||0;
  function syncCaption(){inputs.caption.value=captionTexts.get(captionKey())??(rows[current].sample.caption||'이런 방법이 있었네요');updateCount(inputs.caption);}
  const fixedCaptionShift=frame=>{
    if(mode!=='continuous')return 0;
    const footer=(frame?.cleanup_regions||[]).find(region=>region.role==='source-footer');
    if(!footer)return 0;
    const originalCenter=(footer.y+footer.height/2)/frame.height*100;
    const layout=fixedLayoutFor(rows[current].id,frame);
    return 100-layout.bottom/2-originalCenter;
  };
  const fixedDrawLine=(line,frame)=>{
    if(mode!=='continuous'||line.bind==='caption')return line;
    const baseTop=(frame.video_from?.y||frame.height*.25),nextTop=fixedLayoutFor(rows[current].id,frame).top/100*frame.height;
    const ratio=nextTop/baseTop;
    return {...line,y0:line.y0*ratio,y1:line.y1*ratio,h:line.h*ratio,font_size:(line.font_size||line.h)*Math.min(1.18,Math.max(.82,ratio))};
  };
  const currentDirty=()=>dirtyFields.get(dirtyKey())||new Set();
  const markDirty=bind=>{
    const key=dirtyKey(),set=dirtyFields.get(key)||new Set();set.add(bind);dirtyFields.set(key,set);
  };

  root.querySelectorAll('.layout-a [data-field-key]').forEach(field=>{
    const count=field.querySelector('[data-count]');
    const stepper=document.createElement('span');
    stepper.className='font-stepper';
    stepper.innerHTML='<button type="button" data-font-step="-0.1" title="글자 10% 작게">−</button><output>100%</output><button type="button" data-font-step="0.1" title="글자 10% 크게">＋</button><button type="button" data-position-step="-1" title="위로">↑</button><button type="button" data-position-step="1" title="아래로">↓</button><button type="button" data-field-reset title="프리셋 기본값으로">↺</button>';
    count.before(stepper);
  });
  const captionField=root.querySelector('.layout-a [data-field-key="caption"]');
  if(captionField){
    const captionInput=captionField.querySelector('[data-bind="caption"]');
    captionInput.readOnly=false;captionInput.title='현재 장면의 자막을 편집합니다. 미리보기에서 끌어 위치를 옮길 수 있습니다.';
    captionField.querySelector('.font-stepper').hidden=false;
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
    sceneStrip.innerHTML='<span class="scene-dot"></span><b data-scene-name>1장 · 훅</b><small>장면별 자막 편집 미리보기</small>';
  }
  const colorRow=root.querySelector('.layout-a .color-row');
  if(colorRow)colorRow.innerHTML='<label class="swatch"> <input type="color" data-color-role="white" value="#ffffff"><span>흰색</span></label><label class="swatch"><input type="color" data-color-role="accent" value="#ffe600"><span>강조</span></label><label class="swatch"><input type="color" data-color-role="background" value="#211f19"><span>배경</span></label>';
  const motionPanel=document.createElement('section');
  motionPanel.className='hook-motion';
  motionPanel.innerHTML='<div class="hook-motion-head"><b>훅 시선집중 모션</b><small>첫 장면에만 적용</small></div><div class="hook-motion-grid"><button type="button" class="active" data-hook-motion="zoom-punch">줌 펀치</button><button type="button" data-hook-motion="pop">팝업</button><button type="button" data-hook-motion="slide">슬라이드</button><button type="button" data-hook-motion="flash">플래시</button></div><div class="hook-speed"><span>속도</span><button type="button" data-hook-speed="1.35">느림</button><button type="button" data-hook-speed="1">보통</button><button type="button" class="active" data-hook-speed="0.72">빠름</button></div>';
  root.querySelector('.layout-a .ai-card')?.after(motionPanel);
  const fixedPanel=document.createElement('section');
  fixedPanel.className='fixed-quick-panel';
  fixedPanel.innerHTML='<div class="fixed-quick-head"><b>고정형 빠른 조절</b><button type="button" data-fixed-reset>전체 초기화</button></div><div class="fixed-size-control" data-fixed-size="top"><span>상단 제목칸</span><button type="button" data-fixed-step="-1">−</button><input type="range" min="12" max="50" step="1" data-fixed-range="top"><output>0%</output><button type="button" data-fixed-step="1">＋</button></div><div class="fixed-size-control" data-fixed-size="bottom"><span>하단 자막칸</span><button type="button" data-fixed-step="-1">−</button><input type="range" min="0" max="35" step="1" data-fixed-range="bottom"><output>0%</output><button type="button" data-fixed-step="1">＋</button></div><div class="fixed-palette-row"><button type="button" data-fixed-palette="original">원본</button><button type="button" data-fixed-palette="mint">민트</button><button type="button" data-fixed-palette="yellow">옐로</button><button type="button" data-fixed-palette="pink">핑크</button></div><div class="fixed-color-grid"><label><span>제목 배경</span><input type="color" data-fixed-color="top"></label><label><span>하단 배경</span><input type="color" data-fixed-color="bottom"></label><label><span>제목 1</span><input type="color" data-fixed-color="title1"></label><label><span>제목 2</span><input type="color" data-fixed-color="title2"></label></div>';
  motionPanel.after(fixedPanel);
  const fixedPalettes={mint:{top:'#082923',bottom:'#082923',title1:'#FFFFFF',title2:'#43E2B4'},yellow:{top:'#17140A',bottom:'#17140A',title1:'#FFFFFF',title2:'#FFE24A'},pink:{top:'#24101A',bottom:'#24101A',title1:'#FFFFFF',title2:'#FF78B7'}};
  function syncHookMotionUI(){motionPanel.hidden=mode!=='story'||sceneIndex!==0}
  const minimumFixedTop=frame=>Math.min(46,Math.max(12,Math.ceil((Math.max(0,...(frame?.lines||[]).filter(line=>line.bind!=='caption').map(line=>line.y1))+2)/(frame?.height||1)*100)));
  function syncMediaLayout(){
    const p=rows[current],frame=frameFor(p),bounds=mediaBounds(frame,p?.id);
    Object.assign(media.style,{top:bounds.top+'%',height:bounds.height+'%'});
  }
  function syncFixedPanel(){
    fixedPanel.hidden=mode!=='continuous';if(fixedPanel.hidden)return;
    const p=rows[current],frame=frameFor(p),layout=fixedLayoutFor(p.id,frame),colors=fixedColorsFor(p.id,frame);
    fixedPanel.querySelectorAll('[data-fixed-size]').forEach(row=>{
      const key=row.dataset.fixedSize,input=row.querySelector('input'),output=row.querySelector('output');
      if(key==='top')input.min=String(minimumFixedTop(frame));
      input.value=String(layout[key]);output.textContent=layout[key]+'%';
    });
    fixedPanel.querySelectorAll('[data-fixed-color]').forEach(input=>input.value=colors[input.dataset.fixedColor]);
  }
  function runHookMotion(){
    if(qaMode||motionPanel.hidden||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    [preview,...preview.querySelectorAll('*')].forEach(el=>el.getAnimations?.().forEach(animation=>animation.cancel()));
    const texts=[...layer.querySelectorAll('.precision-text')];
    const timing={duration:620,easing:'cubic-bezier(.18,.88,.25,1)',fill:'both'};
    const time=value=>Math.round(value*hookMotionSpeed);
    const play=(element,keyframes,options)=>{const animation=element.animate(keyframes,options);animation.finished.then(()=>animation.cancel()).catch(()=>{});return animation};
    if(hookMotion==='zoom-punch'){
      play(preview,[
        {transform:'scale(1)',filter:'contrast(1)'},
        {transform:'scale(1.105)',filter:'contrast(1.12)',offset:.32},
        {transform:'scale(1.075) translateX(-3px)',filter:'contrast(1.08)',offset:.48},
        {transform:'scale(1.045) translateX(2px)',filter:'contrast(1.04)',offset:.62},
        {transform:'scale(1)',filter:'contrast(1)'}
      ],{...timing,duration:time(760),easing:'cubic-bezier(.15,.72,.2,1)'});
      texts.forEach((el,index)=>play(el,[
        {opacity:0,transform:'translateY(-18px)'},
        {opacity:1,transform:'translateY(2px)',offset:.68},
        {opacity:1,transform:'translateY(0)'}
      ],{...timing,duration:time(500),delay:time(70+index*70)}));
    }else if(hookMotion==='pop'){
      texts.forEach((el,index)=>play(el,[{opacity:0,transform:'scale(.25)'},{opacity:1,transform:'scale(1.14)',offset:.68},{opacity:1,transform:'scale(1)'}],{...timing,duration:time(520),delay:time(index*90)}));
    }else if(hookMotion==='slide'){
      play(preview,[{transform:'translateX(10px) scale(1.025)'},{transform:'translateX(0) scale(1)'}],{...timing,duration:time(620)});
      texts.forEach((el,index)=>play(el,[{opacity:0,transform:`translateX(${index%2?-46:46}px)`},{opacity:1,transform:'translateX(0)'}],{...timing,duration:time(620),delay:time(index*85)}));
    }else{
      play(preview,[{filter:'brightness(1)'},{filter:'brightness(1.85)',offset:.12},{filter:'brightness(.82)',offset:.25},{filter:'brightness(1)'}],{duration:time(480),easing:'ease-out'});
      texts.forEach((el,index)=>play(el,[{opacity:0,transform:'scale(1.32)'},{opacity:1,transform:'scale(.96)',offset:.7},{opacity:1,transform:'scale(1)'}],{...timing,duration:time(480),delay:time(70+index*55)}));
    }
  }
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
    const reserved=currentHasCaptionSlot();
    const position=captionPositions.get(captionKey())||0;
    const label=root.querySelector('.layout-a .caption-position span');
    if(label)label.textContent=reserved?'✓ 전용 자막칸':'영상 위 자막';
    root.querySelectorAll('.layout-a [data-caption-position]').forEach(button=>{button.hidden=reserved;button.disabled=reserved;button.classList.toggle('active',!reserved&&Number(button.dataset.captionPosition)===position)});
    const guide=root.querySelector('.layout-a .caption-guide');
    if(guide)guide.textContent='이 장면의 자막을 입력하고, 화면에서 끌어 위치를 옮기세요. ＋−로 크기를 조절합니다.';
    captionField?.classList.toggle('reserved-caption',reserved);
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
    if(bind==='caption'){captionPositions.delete(captionKey());captionDrags.delete(captionKey());captionTexts.delete(captionKey());syncCaption();}
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
    const paint=bind&&bind!=='channel'&&mode!=='continuous'?colorFor('background',color):color;
    Object.assign(el.style,{left:x+'%',top:y+'%',width:w+'%',height:h+'%',background:CSS.supports('background',paint)?paint:rgba(paint)});layer.insertBefore(el,badge);return el;
  }
  function fitText(el,startSize,minRatio=.58,checkHeight=false){
    const min=Math.max(5,startSize*minRatio);
    el.style.fontSize=startSize+'px';
    let size=startSize;
    const contentWidth=()=>{const range=document.createRange();range.selectNodeContents(el);return Math.max(el.scrollWidth,range.getBoundingClientRect().width)};
    while(size>min&&(contentWidth()>el.clientWidth+2||(checkHeight&&el.scrollHeight>el.clientHeight+4))){
      size-=.5;el.style.fontSize=size+'px';
    }
  }
  function fitShortemText(){
    if(rows[current].id!=='s0101')return;
    const targets={channel:'[data-preview-channel]',hook1:'[data-preview-hook-1]',hook2:'[data-preview-hook-2]',bodyTitle:'[data-preview-body-title]',caption:'[data-preview-caption]'};
    Object.entries(targets).forEach(([bind,selector])=>root.querySelectorAll('.layout-a '+selector).forEach(el=>{
      el.style.fontSize='';el.style.transform='none';const baseSize=parseFloat(getComputedStyle(el).fontSize)||18;
      fitText(el,baseSize*textScale(bind),.3);
      const range=document.createRange();range.selectNodeContents(el);const width=Math.max(el.scrollWidth,range.getBoundingClientRect().width);
      const xscale=Math.min(1,el.clientWidth/Math.max(1,width)*.98);el.style.transform=xscale<1?`scaleX(${xscale})`:'none';el.style.transformOrigin='center';
    }));
  }
  window.requestShortemFit=()=>requestAnimationFrame(fitShortemText);
  function contrastOutline(el,ln,frame,bind){
    // 배경과 대비가 부족한 글자만 보정한다. 강조 단어도 각각 판정한다.
    const luminance=hex=>{
      if(!/^#[0-9a-f]{6}$/i.test(hex||''))return null;
      const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
      return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
    };
    const y=ln.y0+ln.h/2;
    const region=(frame.cleanup_regions||[]).find(r=>y>=r.y&&y<r.y+r.height);
    const whiteBox=frame.white_box&&y>=frame.white_box.y0&&y<=frame.white_box.y1;
    const fixed=mode==='continuous'?fixedColorsFor(rows[current].id,frame):null;
    const background=bind==='channel'?ln.background:(whiteBox?(frame.white_box.background||'#FFFFFF'):(fixed?(bind==='caption'?fixed.bottom:fixed.top):(region?.background||ln.background||frame.title_bg)));
    const bg=luminance(background);
    const apply=node=>{
      const textColor=node.style.color||el.style.color;
      const rgb=textColor.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      const hex=rgb?'#'+rgb.slice(1,4).map(v=>Number(v).toString(16).padStart(2,'0')).join(''):textColor;
      const fg=luminance(hex);
      const low=bg!==null&&fg!==null&&(Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)<3;
      node.style.webkitTextStroke=low?`1.2px ${bg>.179?'#151515':'#FFFFFF'}`:'0px';
      node.style.paintOrder='stroke fill';
      node.style.textShadow='none';
    };
    apply(el);Array.from(el.children).forEach(apply);
  }
  function addText(text,ln,frame,color,role='center',bind='bodyTitle'){
    const scale=preview.clientHeight/frame.height;
    const measuredBounds=role.includes('left')||role.includes('precision-channel');
    const pad=measuredBounds?Math.max(2,Math.round(4*scale)):0;
    const el=document.createElement('div');el.className='precision-text '+role;el.dataset.editBind=bind;
    const left=measuredBounds?Math.max(0,ln.x0/frame.width*100-1.6):Math.max(1.5,(ln.x0||0)/frame.width*100);
    const right=measuredBounds?Math.max(0,(frame.width-1-ln.x1)/frame.width*100-1.6):Math.max(1.5,(frame.width-1-(ln.x1??frame.width-1))/frame.width*100);
    const fontPx=ln.font_size?ln.font_size*scale:ln.h*scale*1.05;
    // 기본 외곽선/그림자는 제거하고 색 대비 부족 시에만 아래에서 얇게 보정한다.
    const stroke=0,shadowY=0;
    const family=ln.font_family||frame.font_family||'TmonMonsori';
    const weight=ln.font_weight||frame.font_weight||400;
    const letterPx=ln.letter_spacing!=null?ln.letter_spacing*scale:Math.max(-1.5,-.035*fontPx);
    const manualScale=textScale(bind),scaledFont=Math.max(9,fontPx*manualScale);
    const topOffset=(bind==='caption'?captionOffset()+fixedCaptionShift(frame):0)+textOffset(bind);
    const verticalNudge=bind==='channel'?.7:-.35;
    const baseHeight=ln.h/frame.height*100+.9,displayHeight=baseHeight*Math.max(1,manualScale);
    const displayTop=ln.y0/frame.height*100+verticalNudge+topOffset-(displayHeight-baseHeight)/2;
    Object.assign(el.style,{left:left+'%',right:right+'%',top:Math.max(0,displayTop)+'%',height:displayHeight+'%',fontSize:scaledFont+'px',fontFamily:`"${family}",sans-serif`,fontWeight:String(weight),fontStyle:ln.font_style||'normal',letterSpacing:letterPx+'px',color:rgba(color||ln.color||'#fff'),textShadow:shadowY?`0 ${shadowY}px 1px rgba(0,0,0,.88)`:'none',webkitTextStroke:stroke?`${stroke}px #080808`:'0',padding:`0 ${pad}px`,whiteSpace:ln.max_lines>1?'normal':'nowrap',flexWrap:ln.max_lines>1?'wrap':'nowrap',alignContent:ln.max_lines>1?'center':'normal',lineHeight:ln.max_lines>1?'1.05':'1'});
    const fixedColorKey=bind==='hook1'?'title1':(bind==='hook2'||bind==='bodyTitle')?'title2':null;
    const forcedColor=fixedColorKey&&mode==='continuous'&&fixedColors.get(rows[current].id)?.[fixedColorKey];
    if(forcedColor){el.style.color=forcedColor;el.textContent=text||' ';
    }else if(ln.word_colors?.length){
      String(text||' ').split(/\s+/).forEach((word,index,words)=>{const span=document.createElement('span');span.textContent=word;span.style.color=ln.word_colors[index]||ln.color||'#fff';if(index<words.length-1)span.style.marginRight=Math.max(2,fontPx*.11)+'px';el.append(span)});
    }else if(ln.accent_words){
      const words=String(text||' ').split(/\s+/),accent=document.createElement('span'),rest=document.createElement('span');
      accent.textContent=words.slice(0,ln.accent_words).join(' ');accent.style.color=ln.accent;accent.style.marginRight=Math.max(2,fontPx*.11)+'px';
      rest.textContent=words.slice(ln.accent_words).join(' ');el.append(accent,rest);
    }else el.textContent=text||' ';
    contrastOutline(el,ln,frame,bind);
    if(frame.reference_style){el.style.webkitTextStroke=ln.stroke?`${ln.stroke*scale}px #080808`:'0px';el.style.textShadow=ln.shadow_y?`0 ${ln.shadow_y*scale}px ${2*scale}px #000000AA`:'none';}
    if(ln.max_lines>1){el.style.overflowWrap='anywhere';el.style.wordBreak='keep-all';el.style.textWrap='balance';el.style.lineHeight='1.2';}
    layer.insertBefore(el,badge);
    if(bind==='caption'){el.style.left=(left+captionX())+'%';el.style.right=(right-captionX())+'%';}
    const fitKey=`${scaleKey(bind)}:${family}:${weight}:${ln.x0}:${ln.y0}`,chars=Math.max(1,[...String(text||' ')].length),cached=fittedText.get(fitKey);
    if(cached&&chars<=cached.capacity){el.style.fontSize=cached.size+'px';if(cached.letter!=null)el.style.letterSpacing=cached.letter+'px';const xscale=cached.xscale??1;if(xscale<1){el.style.transform=`scaleX(${xscale})`;el.style.transformOrigin=role.includes('left')?'left center':'center';}}
    else {const isStory=mode==='story',manualSize=fontScales.has(scaleKey(bind));if(!manualSize)fitText(el,scaledFont,isStory ? .3 : .12,true);const fitted=parseFloat(el.style.fontSize)||scaledFont;el.style.fontSize=fitted+'px';let fittedLetter=parseFloat(getComputedStyle(el).letterSpacing)||0;const range=document.createRange();range.selectNodeContents(el);const measuredWidth=()=>Math.max(el.scrollWidth,range.getBoundingClientRect().width);const minLetter=isStory?-fitted*.08:-fitted*.3;while(!manualSize&&measuredWidth()>el.clientWidth+2&&fittedLetter>minLetter){fittedLetter-=.2;el.style.letterSpacing=Math.max(minLetter,fittedLetter)+'px';}const overflowScale=el.clientWidth/Math.max(1,measuredWidth())*.98;const xscale=manualSize?1:isStory?Math.min(1,overflowScale):Math.min(Number(ln.scale_x)||1,overflowScale);if(xscale<1){el.style.transform=`scaleX(${xscale})`;el.style.transformOrigin=role.includes('left')?'left center':'center';}fittedText.set(fitKey,{capacity:chars+1,size:fitted,letter:fittedLetter,xscale});}
    return el;
  }
  function renderEdit(){
    [...layer.children].filter(x=>x!==badge).forEach(x=>x.remove());
    const p=rows[current],frame=frameFor(p);if(!frame)return;
    base.hidden=!!frame.design_label;
    const mediaSource=frame.media_source||uniformMedia;if(media.getAttribute('src')!==mediaSource)media.src=mediaSource;
    badge.textContent=frame.design_label?frame.design_label:'원본 실측 편집';
    badge.hidden=!!frame.design_label;
    const dirty=currentDirty();
    const bg=frame.title_bg||frame.top_band?.color||'#111111';
    const fixedLayout=mode==='continuous'?fixedLayoutFor(p.id,frame):null;
    const fixedPaint=mode==='continuous'?fixedColorsFor(p.id,frame):null;
    (frame.cleanup_regions||[]).forEach(region=>{
      if(mode==='continuous'&&(region.role==='original-title'||region.role==='source-footer'))return;
      addPatch(region.y/frame.height*100,region.height/frame.height*100,region.background,(region.x||0)/frame.width*100,(region.width||frame.width)/frame.width*100);
    });
    if(fixedLayout){
      addPatch(0,fixedLayout.top,fixedPaint.top);
      if(fixedLayout.bottom>0)addPatch(100-fixedLayout.bottom,fixedLayout.bottom,fixedPaint.bottom);
    }
    if(dirty.size){
      (frame.boxes||[]).forEach(b=>{const box=addPatch(b.y/frame.height*100,b.height/frame.height*100,b.background,b.x/frame.width*100,b.width/frame.width*100);if(b.border)box.style.border=`${b.border_width||1}px solid ${b.border}`;});
    }
    const designScale=preview.clientHeight/frame.height;
    (frame.surfaces||[]).forEach(s=>{
      const offset=s.bind==='caption'?captionOffset()+textOffset('caption'):0;
      const surface=addPatch(s.y/frame.height*100+offset,s.height/frame.height*100,s.background,s.x/frame.width*100+(s.bind==='caption'?captionX():0),s.width/frame.width*100);
      surface.classList.add('body-material');
      if(s.bind)surface.dataset.editBind=s.bind;
      surface.style.borderRadius=(s.radius||0)*designScale+'px';
      for(const [key,css] of [['border','border'],['borderTop','borderTop'],['borderBottom','borderBottom']])if(s[key])surface.style[css]=`${Math.max(.5,designScale)}px solid ${s[key]}`;
      if(s.shadow)surface.style.boxShadow=s.shadow;
    });
    (frame.ornaments||[]).forEach(o=>{
      const el=document.createElement('i');el.className='body-ornament body-ornament-'+o.type;el.setAttribute('aria-hidden','true');
      Object.assign(el.style,{left:o.x/frame.width*100+'%',top:o.y/frame.height*100+'%',width:o.width/frame.width*100+'%',height:o.height/frame.height*100+'%',color:o.color});
      layer.insertBefore(el,badge);
    });
    const channelBoxes=frame.channel_boxes?.length?frame.channel_boxes:(frame.channel_box?[frame.channel_box]:[]);
    if(dirty.has('channel')&&channelBoxes.length){
      channelBoxes.forEach(c=>{
      if(c.designed){
        const ln={x0:c.x,x1:c.x+c.width,y0:c.y,h:c.height,font_size:c.font_size,font_family:c.font_family,font_weight:c.font_weight,letter_spacing:c.letter_spacing,background:c.background};
        addText(value('channel'),ln,frame,c.color,'center precision-channel','channel');return;
      }
      const scale=preview.clientHeight/frame.height,maxWidth=frame.width*.9,maxX=frame.width*.05;
      const box=addPatch(c.y/frame.height*100,c.height/frame.height*100,c.background,c.x/frame.width*100,c.width/frame.width*100,'channel');
      box.style.borderRadius=((Number(c.radius)||0)*preview.clientHeight/frame.height)+'px';if(c.border)box.style.border=`${Math.max(1,preview.clientHeight/frame.height)}px solid ${c.border}`;
      const channelLine={x0:maxX,x1:maxX+maxWidth,y0:c.y,y1:c.y+c.height,h:c.height,font_size:c.font_size,font_family:c.font_family,font_weight:c.font_weight,letter_spacing:c.letter_spacing,background:c.background,stroke:0,shadow_y:0};
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
      const drawLine=fixedDrawLine(ln,frame),pt=drawLine.patch_top??2,pb=drawLine.patch_bottom??2;
      const offset=(key==='caption'?captionOffset()+fixedCaptionShift(frame):0)+textOffset(key);
      const lineBackground=fixedPaint?(key==='caption'?fixedPaint.bottom:fixedPaint.top):(drawLine.background||bg);
      if(!drawLine.no_patch){
        if(offset)addPatch(Math.max(0,(drawLine.y0-pt)/frame.height*100),(drawLine.h+pt+pb)/frame.height*100,lineBackground,0,100,key);
        if(!drawLine.skip_patch)addPatch(Math.max(0,(drawLine.y0-pt)/frame.height*100+offset),(drawLine.h+pt+pb)/frame.height*100,lineBackground,0,100,key);
        else addPatch(Math.max(0,(drawLine.y0-pt)/frame.height*100+offset),(drawLine.h+pt+pb)/frame.height*100,drawLine.background||frame.boxes?.[0]?.background||bg,Math.max(0,drawLine.x0/frame.width*100-2),(drawLine.x1-drawLine.x0)/frame.width*100+4,key);
      }
      const align=(drawLine.lpct??50)<4&&(drawLine.rpct??50)>10?'left':'center';
      const roleColor=key==='hook2'?'accent':key==='hook1'?'white':null;
      const fixedOverride=mode==='continuous'?fixedColors.get(p.id):null;
      const fixedTextColor=fixedOverride?(key==='hook1'?fixedOverride.title1:(key==='hook2'||key==='bodyTitle')?fixedOverride.title2:null):null;
      addText(value(key),drawLine,frame,fixedTextColor||(roleColor?colorFor(roleColor,drawLine.color):drawLine.color),align,key);
    });
    const wb=frame.white_box;
    if(wb){
      // 원본 설명띠의 글자/흔적을 먼저 완전히 덮고 편집 가능한 텍스트만 다시 올린다.
      addPatch(wb.y0/frame.height*100,(wb.y1-wb.y0+1)/frame.height*100,wb.background||'#FFFFFF',0,100,'white-box');
    }
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
    const frame=frameFor(p),bounds=mediaBounds(frame,p.id);Object.assign(media.style,{top:bounds.top+'%',height:bounds.height+'%'});
    preview.classList.toggle('is-body',mode!=='continuous'&&kind==='body');
    preview.classList.toggle('is-continuous',mode==='continuous');
    const seg=root.querySelector('.layout-a .seg');if(seg)seg.hidden=mode==='continuous';
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    syncCaption();fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();syncHookMotionUI();syncFixedPanel();requestAnimationFrame(runHookMotion);
  }
  function showScene(nextIndex){
    sceneIndex=Math.max(0,Math.min(sceneTotal()-1,nextIndex));
    kind=mode==='continuous'?'hook':sceneIndex===0?'hook':'body';
    if(mode==='continuous'){
      markDirty('caption');
      inputs.caption.value=sceneIndex>0?(rows[current].sample.caption||'이런 방법이 있었네요'):'';
    }
    const p=rows[current],source=imageFor(p,sceneIndex);
    base.src=source;const frame=frameFor(p,sceneIndex),bounds=mediaBounds(frame,p.id);Object.assign(media.style,{top:bounds.top+'%',height:bounds.height+'%'});preview.classList.toggle('is-body',mode!=='continuous'&&kind==='body');
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    syncCaption();fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();syncHookMotionUI();syncFixedPanel();requestAnimationFrame(runHookMotion);
  }
  function selectPreset(index){
    current=index;const p=rows[index];
    if(mode==='continuous')kind='hook';else sceneIndex=kind==='hook'?0:Math.max(1,sceneIndex);
    preview.classList.remove('template-shortem');
    preview.classList.add('template-precision');
    base.hidden=false;media.hidden=false;layer.hidden=false;
    if(mode==='continuous')dirtyFields.set(`${p.id}:frame`,new Set(frameKeys('frame',p)));
    else {dirtyFields.set(`${p.id}:hook`,new Set(frameKeys('hook',p)));dirtyFields.set(`${p.id}:body`,new Set(frameKeys('body',p)));}
    grid.querySelectorAll('[data-p20]').forEach((x,i)=>x.classList.toggle('selected',i===index));
    inputs.channel.value=p.sample.channel||'숏템메이커';inputs.hook1.value=p.sample.hook1;inputs.hook2.value=p.sample.hook2;inputs.bodyTitle.value=p.sample.bodyTitle;inputs.caption.value=p.sample.caption||(mode==='continuous'&&sceneIndex>0?'이런 방법이 있었네요':'');
    for(const bind of ['hook1','hook2','bodyTitle','caption'])inputs[bind].placeholder='';
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
    if(input.dataset.bind==='caption')captionTexts.set(captionKey(),input.value);
    markDirty(input.dataset.bind);preview.classList.remove('is-pristine');renderEdit();
  }));
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-font-step]');if(!button)return;
    const bind=button.closest('[data-field-key]').dataset.fieldKey;
    const next=Math.min(3,Math.max(.5,textScale(bind)+Number(button.dataset.fontStep)));
    if(Math.abs(next-1)<.001)fontScales.delete(scaleKey(bind));else fontScales.set(scaleKey(bind),next);[...fittedText.keys()].filter(key=>key.startsWith(scaleKey(bind)+':')).forEach(key=>fittedText.delete(key));markDirty(bind);preview.classList.remove('is-pristine');updateSteppers();renderEdit();
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
  motionPanel.addEventListener('click',event=>{
    const choice=event.target.closest('[data-hook-motion]');
    if(choice){hookMotion=choice.dataset.hookMotion;motionPanel.querySelectorAll('[data-hook-motion]').forEach(button=>button.classList.toggle('active',button===choice));runHookMotion();return}
    const speed=event.target.closest('[data-hook-speed]');
    if(speed){hookMotionSpeed=Number(speed.dataset.hookSpeed);motionPanel.querySelectorAll('[data-hook-speed]').forEach(button=>button.classList.toggle('active',button===speed));runHookMotion();return}
  });
  const applyFixedSize=(key,rawValue)=>{
    if(mode!=='continuous')return;
    const p=rows[current],frame=frameFor(p),currentLayout={...fixedLayoutFor(p.id,frame)};
    const min=key==='top'?minimumFixedTop(frame):0,max=key==='top'?50:35;
    currentLayout[key]=Math.round(Math.max(min,Math.min(max,Number(rawValue))));
    if(currentLayout.top+currentLayout.bottom>70)currentLayout[key]=70-currentLayout[key==='top'?'bottom':'top'];
    fixedLayouts.set(p.id,currentLayout);fittedText.clear();preview.classList.remove('is-pristine');syncMediaLayout();renderEdit();syncFixedPanel();
  };
  fixedPanel.addEventListener('input',event=>{
    const range=event.target.closest('[data-fixed-range]');
    if(range){applyFixedSize(range.dataset.fixedRange,range.value);return}
    const color=event.target.closest('[data-fixed-color]');
    if(color&&mode==='continuous'){
      const p=rows[current],next={...(fixedColors.get(p.id)||{})};next[color.dataset.fixedColor]=color.value;fixedColors.set(p.id,next);
      preview.classList.remove('is-pristine');renderEdit();syncFixedPanel();
    }
  });
  fixedPanel.addEventListener('click',event=>{
    const step=event.target.closest('[data-fixed-step]');
    if(step){const row=step.closest('[data-fixed-size]'),key=row.dataset.fixedSize;applyFixedSize(key,Number(row.querySelector('input').value)+Number(step.dataset.fixedStep));return}
    const palette=event.target.closest('[data-fixed-palette]');
    if(palette&&mode==='continuous'){
      const p=rows[current];
      if(palette.dataset.fixedPalette==='original')fixedColors.delete(p.id);else fixedColors.set(p.id,{...fixedPalettes[palette.dataset.fixedPalette]});
      preview.classList.remove('is-pristine');renderEdit();syncFixedPanel();return;
    }
    if(event.target.closest('[data-fixed-reset]')&&mode==='continuous'){
      const p=rows[current];fixedLayouts.delete(p.id);fixedColors.delete(p.id);fittedText.clear();syncMediaLayout();renderEdit();syncFixedPanel();
    }
  });
  const saveButton=root.querySelector('.layout-a .secondary');
  saveButton?.addEventListener('click',()=>{
    const p=rows[current],snapshot={mode,presetId:p.id,sceneIndex,frameKind:frameKind(),hookMotion,hookMotionSpeed,text:Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value])),fontScales:Object.fromEntries(fontScales),textOffsets:Object.fromEntries(textOffsets),colors:Object.fromEntries(colorOverrides),fixedLayouts:Object.fromEntries(fixedLayouts),fixedColors:Object.fromEntries(fixedColors),captionTexts:Object.fromEntries(captionTexts),captionDrags:Object.fromEntries(captionDrags),captionPositions:Object.fromEntries(captionPositions)};
    localStorage.setItem('scene_style_preset',JSON.stringify(snapshot));saveButton.textContent='✓ 현재 설정 저장됨';setTimeout(()=>saveButton.textContent='현재 설정 저장',1400);
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-caption-position]');if(!button)return;
    captionPositions.set(captionKey(),Number(button.dataset.captionPosition));markDirty('caption');updateCaptionButtons();renderEdit();
  });
  addEventListener('resize',()=>{if(!preview.classList.contains('is-pristine'))renderEdit()});
  let captionDrag=null;
  preview.addEventListener('pointerdown',event=>{
    if(event.button!==0||!event.target.closest('[data-edit-bind="caption"]'))return;
    const rect=preview.getBoundingClientRect(),text=layer.querySelector('.precision-text[data-edit-bind="caption"]');if(!text)return;
    const bounds=text.getBoundingClientRect(),origin=captionDrags.get(captionKey())||{x:0,y:0};
    captionDrag={pointer:event.pointerId,startX:event.clientX,startY:event.clientY,rect,origin,bounds};
    preview.setPointerCapture(event.pointerId);event.preventDefault();
  });
  preview.addEventListener('pointermove',event=>{
    if(!captionDrag||event.pointerId!==captionDrag.pointer)return;
    const d=captionDrag;
    const dx=Math.max(Math.min(0,d.rect.left-d.bounds.left),Math.min(Math.max(0,d.rect.right-d.bounds.right),event.clientX-d.startX));
    const dy=Math.max(Math.min(0,d.rect.top-d.bounds.top),Math.min(Math.max(0,d.rect.bottom-d.bounds.bottom),event.clientY-d.startY));
    captionDrags.set(captionKey(),{x:d.origin.x+dx/d.rect.width*100,y:d.origin.y+dy/d.rect.height*100});
    markDirty('caption');renderEdit();
  });
  for(const type of ['pointerup','pointercancel','lostpointercapture'])preview.addEventListener(type,()=>{captionDrag=null;});
  const premiumFaces=['SBAggroB','YgJalnan','JalnanGothic','Jalnan2','GothicA1Black','GmarketSansBold','GasoekOne','Cafe24Ohsquare','KCCGanpan','BinggraeBold','BlackHanSans','Pretendard'];
  Promise.all(premiumFaces.map(family=>document.fonts?.load?.(`400 32px "${family}"`))).then(()=>{fittedText.clear();renderEdit()});
  document.fonts?.addEventListener?.('loadingdone',()=>{fittedText.clear();renderEdit()});
  saveButton&&(saveButton.textContent='현재 설정 저장');
  const query=new URLSearchParams(location.search),initialPreset=Math.max(0,Number(query.get('preset'))||0);
  if(query.get('mode')==='continuous'){modeBar.querySelector('[data-template-mode="continuous"]').click();if(initialPreset<rows.length)selectPreset(initialPreset)}else selectPreset(Math.min(initialPreset,rows.length-1));
  if(mode==='story'&&query.get('frame')==='body')showFrame('body');
  if(!qaMode){
    try{
      const saved=JSON.parse(localStorage.getItem('scene_style_preset')||'null');
      if(saved){
        if(saved.presetId==='t11'&&saved.text?.channel==='이븐쇼핑')saved.text.channel='숏템메이커';
        for(const [name,map] of Object.entries({fontScales,textOffsets,colors:colorOverrides,fixedLayouts,fixedColors,captionTexts,captionDrags,captionPositions}))for(const [key,value] of Object.entries(saved[name]||{}))map.set(key,value);
        if(!query.has('preset')&&!query.has('mode')){
          modeBar.querySelector(`[data-template-mode="${saved.mode==='continuous'?'continuous':'story'}"]`).click();
          const index=rows.findIndex(p=>p.id===saved.presetId);if(index>=0)selectPreset(index);
        }
        if(rows[current].id===saved.presetId){
          const savedScene=saved.sceneIndex??(saved.frameKind==='body'?1:0);
          showScene(query.get('frame')==='hook'?0:query.get('frame')==='body'?Math.max(1,savedScene):savedScene);
          for(const [key,text] of Object.entries(saved.text||{}))if(inputs[key]&&key!=='caption'){inputs[key].value=text;markDirty(key);updateCount(inputs[key]);}
        }
        hookMotion=saved.hookMotion||hookMotion;hookMotionSpeed=saved.hookMotionSpeed||hookMotionSpeed;renderEdit();
      }
    }catch(error){console.warn('저장 설정 복원 실패',error);}
  }
})();
