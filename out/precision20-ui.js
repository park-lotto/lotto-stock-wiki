(()=>{
  const storyRows=window.PRECISION20||[],fixedRows=window.CONTINUOUS20||[];
  let rows=storyRows,mode='story';
  const root=document;
  const query=new URLSearchParams(location.search),qaMode=query.has('qa');
  const labMode=query.get('lab')==='1';
  const preview=root.getElementById('a-live-preview');
  const grid=root.querySelector('.layout-a .preset-grid');
  if(!rows.length||!preview||!grid)return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const compact=n=>n?new Intl.NumberFormat('ko-KR',{notation:n>=1e6?'compact':'standard',maximumFractionDigits:1}).format(n)+'회':'시인성 선별';
  const displayName=p=>p.id==='s0101'?'숏템 기본형':p.name;
  const fontNames={SBAggroB:'강렬한 어그로체',YgJalnan:'친근한 잘난체',Cafe24Ohsquare:'각진 카페24',BinggraeBold:'부드러운 빙그레',Jalnan2:'잘난체 2',JalnanGothic:'잘난고딕',GasoekOne:'묵직한 가석체',GmarketSansBold:'지마켓 산스',TmonMonsori:'티몬 몬소리',BlackHanSans:'검은고딕',GothicA1Black:'고딕 A1',Pretendard:'깔끔한 프리텐다드'};
  const fontLabel=p=>{const family=(p.hook||p.frame)?.lines?.[0]?.font_family;return fontNames[family==='PretendardXBold'?'Pretendard':family]||'템플릿 전용 서체'};
  const uniformMedia='assets/scene-style/uniform-household-demo.png';
  const fixedLayouts=new Map(),fixedColors=new Map(),captionLayouts=new Map();
  const fixedBaseLayout=frame=>{
    const footer=(frame?.cleanup_regions||[]).find(region=>region.role==='source-footer');
    // 09-19 사장님: 고정형은 제목칸 높이도 20종을 하나로(원본은 25~33%로 제각각이라 영상 시작 줄이 안 맞았다)
    const original=Math.round((frame?.video_from?.y||0)/(frame?.height||1)*100);
    return {top:mode==='continuous'?FIXED_TITLE.band:original,bottom:0};
  };
  const layoutKey=(presetId,frame)=>presetId.startsWith('fixed_')?presetId:`${presetId}:${frame===storyRows.find(p=>p.id===presetId)?.hook?'hook':'body'}`;
  // 하단 칸(2026-09-18 사장님 "빠른조절에 하단 칸도 만들어서 올리고 내릴수있게") — 저장한 값만 쓰고 기본은 0.
  const fixedLayoutFor=(presetId,frame)=>{const saved=fixedLayouts.get(layoutKey(presetId,frame))||{};return {...fixedBaseLayout(frame),...saved,bottom:Number(saved.bottom)||0};};
  const fixedBaseColors=frame=>{
    const titleLines=(frame?.lines||[]).filter(line=>line.bind!=='caption');
    const footer=(frame?.cleanup_regions||[]).find(region=>region.role==='source-footer');
    return {top:frame?.title_bg||frame?.top_band?.color||'#000000',bottom:footer?.background||'#000000',title1:titleLines[0]?.color||'#FFFFFF',title2:titleLines[1]?.color||titleLines[0]?.color||'#FFFFFF'};
  };
  const readableInk=background=>{
    const rgb=(background.match(/[a-f\d]{2}/gi)||[]).slice(0,3).map(n=>parseInt(n,16)/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);
    const luminance=rgb.length===3?rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722:0;
    return luminance>.179?'#111111':'#FFFFFF';
  };
  const fixedColorsFor=(presetId,frame)=>{
    const paint=fixedColors.get(layoutKey(presetId,frame))||{};
    return {...fixedBaseColors(frame),channel:paint.top?readableInk(paint.top):(frame.channel_box?.color||frame.channel_boxes?.[0]?.color||'#FFFFFF'),...paint};
  };
  const captionSource=frame=>{
    const ln=(frame.lines||[]).find(l=>l.bind==='caption')||(frame===rows[current]?.body?frame.white_box?.text:null);
    const start=frame.video_from?.y||0;
    const surface=ln&&(frame.surfaces||[]).find(s=>s.y<=ln.y0+ln.h/2&&s.y+s.height>=ln.y0+ln.h/2&&s.y>start*.45);
    const band=frame===rows[current]?.body&&frame.white_box?{y:frame.white_box.y0,height:frame.white_box.y1-frame.white_box.y0,background:frame.white_box.background}:surface;
    const cut=ln&&ln.y0<start?(band?.y??ln.y0):start;
    // 고정형 자막칸 높이는 위시언니(6.5%) 하나로 통일(2026-09-18 사장님 "딱 이 사이즈로 다들 해줘야 비례가 맞지").
    //   실측: 20종 중 14종이 원본 측정값 상한 17.9%라 제목보다 자막칸이 두꺼웠다. 사용자가 저장한 높이는 그대로 우선.
    const measured=Math.max(5,Math.min(18,(band?.height||ln?.h||frame.height*.07)/frame.height*100));
    return {ln,cut,background:band?.background||ln?.background||'#FFFFFF',height:mode==='continuous'?6.5:(isStoryBody(frame)?STORY_BODY.capH:measured)};
  };
  // 고정형은 훅이 없다 — '훅 말자막 숨김'(이븐쇼핑 큰 제목용)이 첫 장면 자막까지 지우지 않게 항상 보인다(2026-09-18 실측: LAB 1/23 자막 없음).
  const captionVisible=()=>mode==='continuous'||sceneContext?.scenes?.[sceneIndex]?.caption_visible!==false;
  const hasEditableCaption=()=>captionVisible()&&(mode==='continuous'||kind==='body');
  const captionSettings=()=>{
    const frame=frameFor(rows[current]),source=captionSource(frame),saved=captionLayouts.get(captionKey())||{};
    return {placement:captionDrags.has(captionKey())?'free':'title',w:100,h:source.height,background:source.background,color:source.ln?.color||'#111111',...saved};
  };
  const titleHeight=frame=>{
    const original=(frame.video_from?.y||0)/frame.height*100,cut=captionSource(frame).cut/frame.height*100;
    const configured=fixedLayoutFor(rows[current].id,frame).top;
    if(isStoryBody(frame)&&!fixedLayouts.get(layoutKey(rows[current].id,frame)))return STORY_BODY.cut;
    return mode==='continuous'||fixedLayouts.get(layoutKey(rows[current].id,frame))?.titleOnly?configured:configured*cut/Math.max(.01,original);
  };
  const mediaBounds=(frame,presetId)=>{
    if(!frame||noTemplate)return {top:0,height:100};   // 템플릿 없음 = 영상이 화면 전체
    const top=titleHeight(frame)+(hasEditableCaption()&&captionSettings().placement==='title'?captionSettings().h:0);
    const bottom=fixedLayoutFor(presetId||rows[current].id,frame).bottom;
    return {top,height:Math.max(10,100-top-bottom)};
  };
  const fixedThumb=p=>`assets/scene-style/thumbnails/fixed-${p.source_id}.png`;
  const storyThumb=(p,kind)=>`assets/scene-style/thumbnails/story-${p.id}-${kind}.png`;
  const storyHasCaptionSlot=frame=>frame?.caption_slot?frame.caption_slot.mode==='reserved':!!frame?.white_box||(frame?.cleanup_regions||[]).some(r=>r.role==='source-footer');
  const presetHasCaptionSlot=p=>p.mode==='continuous'?p.frame?.caption_slot?.mode==='reserved':storyHasCaptionSlot(p.body);
  const captionBadge=p=>presetHasCaptionSlot(p)?'<span class="caption-kind reserved">자막칸</span>':'<span class="caption-kind overlay">영상 위</span>';
  const renderGrid=()=>{
    const count=root.querySelector('.layout-a .pane-head .count');if(count)count.textContent=`${storyRows.length+fixedRows.length}개`;
    grid.innerHTML='<button class="preset-card none-card" data-none><span class="check">✓</span><div class="none-thumb">원본 영상<br>그대로</div><b>템플릿 없음</b><small>제목·자막 꾸미기 없이</small></button>'+rows.map((p,i)=>mode==='continuous'
      ? `<button class="preset-card fixed-card${i===0?' selected':''}" data-p20="${i}"><span class="check">✓</span>${captionBadge(p)}<div class="fixed-thumb" style="background-image:url('${fixedThumb(p)}')"></div><b>${esc(p.name)}</b><small>${esc(fontLabel(p))} · 고정형</small></button>`
      : `<button class="preset-card${i===0?' selected':''}" data-p20="${i}"><span class="check">✓</span>${captionBadge(p)}<div class="thumb-pair"><img src="${storyThumb(p,'hook')}"><img src="${storyThumb(p,'body')}"></div><b>${esc(displayName(p))}</b><small>${esc(fontLabel(p))} · 훅+본문</small></button>`).join('');
  };
  const presetPane=grid.closest('.pane'),modeBar=document.createElement('div');modeBar.className='template-mode-bar';
  modeBar.innerHTML='<button type="button" data-template-mode="story" class="active">썰쇼핑형 <small>20</small></button><button type="button" data-template-mode="continuous">전장면 고정형 <small>20</small></button>';
  presetPane.querySelector('.pane-head').after(modeBar);renderGrid();
  // 왼쪽 맨 위 탭(2026-09-19 사장님): '템플릿 선택' 머리말 자리에 [장면 템플릿 | 폰트 템플릿].
  //   오른쪽 문구/효과 탭과 같은 .tool-tabs 모양. 폰트 템플릿(채널명·제목·자막 한 세트)은 다음 단계 — 지금은 자리만.
  {
    const head=presetPane.querySelector('.pane-head'),leftTabs=document.createElement('div');
    leftTabs.className='tool-tabs left-pane-tabs';
    leftTabs.innerHTML='<button type="button" class="active" data-left-tab="scene">장면 템플릿</button><button type="button" data-left-tab="font">폰트 템플릿</button>';
    const fontPane=document.createElement('div');fontPane.className='font-template-pane';fontPane.hidden=true;
    const drawFontSets=()=>{fontPane.innerHTML='<div class="font-set-grid">'+[{id:'',name:'기본 (강렬 어그로)',channel:'SBAggroB',title:'SBAggroB',caption:'BlackHanSans'},...FONT_SETS].map(f=>`<button type="button" class="font-set-card${f.id===fontSet?' selected':''}" data-font-set="${f.id}"><span class="fs-ch" style="font-family:'${f.channel||'Pretendard'}'">숏템메이커</span><span class="fs-title" style="font-family:'${f.title||'Pretendard'}'">제목 첫줄<br><em>제목 둘째줄</em></span><span class="fs-cap" style="font-family:'${f.caption||'Pretendard'}'">자막 예시</span><b>${f.name}</b></button>`).join('')+'</div>';};
    window.addEventListener('scene-style-fontset',()=>{if(!fontPane.hidden)drawFontSets();});   // FONT_SETS는 아래에서 정의되므로 탭을 열 때 그린다
    fontPane.addEventListener('click',event=>{const c=event.target.closest('[data-font-set]');if(!c)return;fontSet=c.dataset.fontSet;fittedText.clear();drawFontSets();renderEdit();rememberLocal({fontSet});});   /* 저장 버튼을 안 눌러도 기억 — 새로고침하면 풀리던 문제 */
    head.hidden=true;head.before(leftTabs);grid.after(fontPane);
    const sceneParts=[modeBar,grid];
    leftTabs.addEventListener('click',event=>{
      const b=event.target.closest('[data-left-tab]');if(!b)return;
      leftTabs.querySelectorAll('[data-left-tab]').forEach(x=>x.classList.toggle('active',x===b));
      const font=b.dataset.leftTab==='font';sceneParts.forEach(el=>el.hidden=font);fontPane.hidden=!font;if(font)drawFontSets();
    });
    const css=document.createElement('style');
    css.textContent='.font-template-pane{min-height:0;flex:1;overflow-y:auto;overscroll-behavior:contain;padding-right:6px;scrollbar-color:#35505b #09161f;scrollbar-width:thin}.font-set-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.font-set-card{display:grid;gap:4px;justify-items:start;text-align:left;padding:10px;border:1px solid #294451;border-radius:12px;background:#1b1b1b;color:#fff;cursor:pointer}.font-set-card.selected{border-color:#43e2b4;box-shadow:0 0 0 2px #43e2b455}.font-set-card .fs-ch{background:#000;border-radius:4px;padding:1px 7px;font-size:12px}.font-set-card .fs-title{font-size:19px;line-height:1.15}.font-set-card .fs-title em{font-style:normal;color:#ffe500}.font-set-card .fs-cap{background:#fff;color:#111;padding:1px 7px;font-size:14px}.font-set-card b{font:800 12px system-ui,sans-serif;color:#9eb0b9;margin-top:4px}.font-set-card.selected b{color:#63edc6}.layout-a .pane-head[hidden]{display:none!important}.left-pane-tabs{margin:0 0 12px}.template-mode-bar[hidden],.preset-grid[hidden]{display:none!important}.font-template-empty{border:1px dashed #294451;border-radius:12px;padding:28px 16px;text-align:center;display:grid;gap:6px;color:#8fa3ad}.font-template-empty b{color:#e8f3f0;font-size:14px}';
    document.head.append(css);
  }

  preview.classList.add('is-pristine');
  const base=document.createElement('img');base.className='precision-base';
  const media=document.createElement('img');media.className='precision-media';media.src=uniformMedia;media.alt='공통 생활용품 시연 장면';
  const layer=document.createElement('div');layer.className='precision-edit-layer';
  const sourceClean=document.createElement('div');sourceClean.className='precision-source-cleanup';preview.append(sourceClean);
  const badge=document.createElement('div');badge.className='precision-badge';badge.textContent='원본 실측 편집';layer.appendChild(badge);
  preview.append(base,media,layer);

  // 템플릿 없음(2026-09-18 사장님 "템플릿 없는 거 쓰는 사람들") — 선택하면 snapshot()이 null을 내고 제작소가 그대로 서버에 저장,
  //   최종 렌더(video_assemble)는 scene_style이 비면 꾸미기를 건너뛴다.
  let noTemplate=false;
  let current=0,kind='hook',sceneIndex=0,hookMotion='zoom-punch',hookBandMotion='',bodyCaptionMotion='',fontSet='',hookMotionSpeed=.72,hookCaptionMode='visible';
  const fontScales=new Map();
  const fittedText=new Map();
  const textOffsets=new Map();
  const textDrags=new Map();   // 제목·채널명을 마우스로 옮긴 양(칸 기준 %)
  const colorOverrides=new Map();
  const dirtyFields=new Map();
  const captionPositions=new Map();
  const captionTexts=new Map(),captionDrags=new Map();
  const originalCaption=root.querySelector('.layout-a [data-bind="caption"]');
  if(originalCaption?.tagName==='INPUT'){
    const textarea=document.createElement('textarea');for(const a of originalCaption.attributes)if(a.name!=='value')textarea.setAttribute(a.name,a.value);
    textarea.value=originalCaption.value;textarea.rows=3;originalCaption.replaceWith(textarea);
  }
  const inputs=Object.fromEntries([...root.querySelectorAll('.layout-a [data-bind]')].map(x=>[x.dataset.bind,x]));
  const value=k=>inputs[k]?.value||' ';
  const rgba=hex=>hex&&/^#[0-9a-f]{6}$/i.test(hex)?hex:'#111111';
  const rememberedBranding=()=>{try{return JSON.parse(localStorage.getItem('scene_style_branding')||'{}')}catch{return {}}};
  let sceneContext=null,effects={},branding=labMode?{}:rememberedBranding();
  const sceneKind=index=>sceneContext?.scenes?.[index]?.kind||(index===0?'hook':'body');
  const frameFor=(p,index=sceneIndex)=>p.mode==='continuous'?p.frame:p[sceneKind(index)];
  const imageFor=(p,index=sceneIndex)=>p.mode==='continuous'?p.frame_image:(sceneKind(index)==='hook'?p.hook_image:p.body_image);
  const frameKind=()=>mode==='continuous'?'frame':kind;
  const scaleKey=bind=>`${rows[current].id}:${frameKind()}:${bind}${bind==='caption'?':'+sceneIndex:''}`;
  const BODY_CAPTION_SCALE=1.3;   // 09-19 사장님: 본문 자막 기본 130%(자막 칸 위치·높이는 그대로)
  const textScale=bind=>fontScales.get(scaleKey(bind))||(bind==='caption'&&mode==='story'&&sceneIndex>0?BODY_CAPTION_SCALE:1);
  const textOffset=bind=>textOffsets.get(scaleKey(bind))||0;
  const colorKey=role=>`${rows[current].id}:${frameKind()}:${role}`;
  const colorFor=(role,fallback)=>colorOverrides.get(colorKey(role))||fallback;
  const dirtyKey=()=>`${rows[current].id}:${frameKind()}`;
  const captionKey=()=>`${rows[current].id}:${mode}:${sceneIndex}:caption`;
  const currentHasCaptionSlot=()=>mode==='continuous'?frameFor(rows[current])?.caption_slot?.mode==='reserved':kind==='body'&&storyHasCaptionSlot(frameFor(rows[current]));
  const captionOffset=()=>(captionDrags.get(captionKey())?.y||0)+(captionPositions.get(captionKey())||0)*6;
  const captionX=()=>captionDrags.get(captionKey())?.x||0;
  function syncCaption(){inputs.caption.value=captionTexts.get(captionKey())??sceneContext?.scenes?.[sceneIndex]?.caption??(rows[current].sample.caption||'이런 방법이 있었네요');updateCount(inputs.caption);}
  const fixedCaptionShift=frame=>{
    if(mode!=='continuous')return 0;
    const footer=(frame?.cleanup_regions||[]).find(region=>region.role==='source-footer');
    if(!footer)return 0;
    const originalCenter=(footer.y+footer.height/2)/frame.height*100;
    const layout=fixedLayoutFor(rows[current].id,frame);
    return 100-layout.bottom/2-originalCenter;
  };
  // 고정형 20종 제목 배치 표준(2026-09-19 사장님): 원본마다 채널명과 제목 사이 빈칸이 5~12%씩 제각각이었다.
  //   이제 제목칸 높이(T)에 대한 같은 비율로 다시 놓는다 — 채널명 아래 곧바로 제목, 줄 간격·글자 크기도 T 비례.
  //   한 곳에서만 정한다(미리보기·최종 렌더 모두 이 함수를 거친다). 사용자가 −/＋로 키운 값은 그 뒤에 곱해진다.
  // 09-19 사장님: 썰쇼핑형 본문도 이븐쇼핑 비율로 통일(원본은 제목 시작 13~21%, 영상 시작 29~39%로 제각각이었다).
  //   cut=자막 칸 시작(%), capH=자막 칸 높이(%), title=cut 대비 제목 위치·높이. 여기 한 곳에서만 정한다.
  const STORY_BODY={cut:21,capH:10,titleTop:.52,titleH:.30,font:.76};
  const isStoryBody=frame=>mode==='story'&&frame===rows[current]?.body;
  const WRAP3=['bodyTitle','caption'],CHANNEL_MAX=.045;   // 본문 제목·자막 3줄 허용 / 채널명 글자 크기 상한(화면 높이 대비)
  const FIXED_TITLE={band:26,first:.33,pad:.06,line:.25,gap:.045,fontOfLine:.76};   // band=제목칸 높이(%), pad=자막 칸 앞 여백
  // 본문 제목은 자막 칸 시작(cut) 기준 같은 자리에 둔다
  const storyBodyLine=(line,frame)=>{
    if(!isStoryBody(frame)||line.bind!=='bodyTitle')return line;
    const cut=titleHeight(frame)/100*frame.height,y0=cut*STORY_BODY.titleTop,h=cut*STORY_BODY.titleH;
    return {...line,y0,y1:y0+h,h,font_size:h*STORY_BODY.font};
  };
  const fixedDrawLine=(line,frame)=>{
    if(mode!=='continuous'||line.bind==='caption')return line;
    const T=fixedLayoutFor(rows[current].id,frame).top/100*frame.height;
    const order=['hook1','hook2','bodyTitle'].indexOf(line.bind);
    if(order<0||!T){   // 채널명 등 제목이 아닌 줄은 예전처럼 칸 높이에 맞춰 비례 이동
      const baseTop=(frame.video_from?.y||frame.height*.25),ratio=T/baseTop;
      // 09-19 사장님 '비율로 글자 크기 줄이지 마라' — 자리만 옮기고 글자 크기는 원본 그대로 둔다
      return {...line,y0:line.y0*ratio,y1:line.y1*ratio,h:line.h*ratio,font_size:line.font_size||line.h};
    }
    // 제목 줄 수에 맞춰 칸 안에 들어가게 계산한다(3줄짜리가 자막 칸을 덮던 것)
    const count=Math.max(1,(frame.lines||[]).filter(l=>['hook1','hook2','bodyTitle'].includes(l.bind)).length);
    const pad=FIXED_TITLE.pad+Math.max(0,count-2)*.05;   // 줄이 많을수록 자막 칸 앞 여백을 더 둔다(3줄에서 1%까지 붙었다)
    const room=1-FIXED_TITLE.first-pad,lineH=Math.min(FIXED_TITLE.line,(room-FIXED_TITLE.gap*(count-1))/count);
    const y0=T*(FIXED_TITLE.first+order*(lineH+FIXED_TITLE.gap)),h=T*lineH;
    // 글자 크기는 기준 칸(FIXED_TITLE.band)으로 고정 — 칸을 올리고 내려도 글자는 그대로(사장님 09-18·09-19)
    const baseBand=FIXED_TITLE.band/100*frame.height;
    return {...line,y0,y1:y0+h,h,font_size:baseBand*lineH*FIXED_TITLE.fontOfLine};
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
    controls.innerHTML='<button type="button" data-caption-placement="title">제목 아래</button><button type="button" data-caption-placement="free">자유 이동</button><label>자막박스 너비<input type="range" data-caption-layout="w" min="20" max="100" step="1"></label><label>자막박스 높이<input type="range" data-caption-layout="h" min="4" max="25" step="1"></label><label>자막박스 색<input type="color" data-caption-layout="background"></label><label>자막 색<input type="color" data-caption-layout="color"></label>';
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
  motionPanel.innerHTML='<div class="hook-motion-head"><b>훅 시선집중 모션</b><small>첫 장면에만 적용</small></div><div class="hook-motion-grid"><button type="button" class="active" data-hook-motion="zoom-punch">줌 펀치</button><button type="button" data-hook-motion="pop">팝업</button><button type="button" data-hook-motion="slide">슬라이드</button><button type="button" data-hook-motion="flash">플래시</button><button type="button" data-hook-motion="push-in">천천히 확대</button><button type="button" data-hook-motion="shake">떨림</button></div><div class="hook-speed hook-band-motion"><span>흰 띠</span><button type="button" data-hook-band-motion="">없음</button><button type="button" data-hook-band-motion="rise">스윽 올라오기</button><button type="button" data-hook-band-motion="grow">천천히 확대</button></div><div class="hook-speed"><span>속도</span><button type="button" data-hook-speed="1.35">느림</button><button type="button" data-hook-speed="1">보통</button><button type="button" class="active" data-hook-speed="0.72">빠름</button></div>';
  root.querySelector('.layout-a .ai-card')?.after(motionPanel);
  // 본문 모션(2026-09-19 사장님): 본문 장면 자막이 바뀔 때마다 들어오는 효과. 흰 띠 스윽/확대를 자막 효과로 넓혔다.
  //   값 목록은 BODY_CAPTION_MOTIONS 한 곳 — 버튼·미리보기·렌더(captionEnterAt)가 모두 여기서 읽는다. 서버 허용값은 scene_style.py와 짝.
  // 폰트 템플릿(2026-09-19 사장님): 채널명 · 제목 · 자막 폰트를 한 세트로. 모든 장면 공통.
  //   편집기 @font-face로 등록된 글꼴만 쓴다(최종 영상은 이 페이지를 그대로 찍으므로 같은 글꼴이 나온다).
  //   초안 10종 — 사장님이 고르고 고칠 목록. 서버 허용값(scene_style.py)은 id 형식만 검사한다.
  const FONT_SETS=[
    {id:'aggro',name:'강렬 어그로',channel:'SBAggroB',title:'SBAggroB',caption:'BlackHanSans'},
    {id:'jalnan',name:'잘난 쇼핑',channel:'YgJalnan',title:'YgJalnan',caption:'Pretendard'},
    {id:'blackhan',name:'검은고딕 뉴스',channel:'BlackHanSans',title:'BlackHanSans',caption:'Pretendard'},
    {id:'gmarket',name:'G마켓 깔끔',channel:'GmarketSansBold',title:'GmarketSansBold',caption:'GmarketSansBold'},
    {id:'baemin',name:'배민 도현',channel:'BMDOHYEON',title:'BMDOHYEON',caption:'BMJUA'},
    {id:'cafe24',name:'카페24 각진',channel:'Cafe24Ohsquare',title:'Cafe24Ohsquare',caption:'Pretendard'},
    {id:'gasoek',name:'묵직 가석',channel:'GasoekOne',title:'GasoekOne',caption:'BlackHanSans'},
    {id:'binggrae',name:'부드러운 빙그레',channel:'BinggraeBold',title:'BinggraeBold',caption:'BMJUA'},
    {id:'ganpan',name:'간판체',channel:'KCCGanpan',title:'KCCGanpan',caption:'GmarketSansBold'},
    {id:'jalnangothic',name:'잘난고딕',channel:'JalnanGothic',title:'Jalnan2',caption:'JalnanGothic'},
    {id:'bagel',name:'베이글 팝',channel:'BagelFatOne',title:'BagelFatOne',caption:'BMJUA'},
    {id:'dongle',name:'동글 귀여움',channel:'DongleBold',title:'DongleBold',caption:'GmarketSansBold'},
    {id:'kkubulim',name:'꾸불림 재미',channel:'Kkubulim',title:'Kkubulim',caption:'BMJUA'},
    {id:'myeongjo',name:'명조 고급',channel:'NanumMyeongjoEB',title:'NanumMyeongjoEB',caption:'RIDIBatang'},
    {id:'ridi',name:'리디 감성',channel:'RIDIBatang',title:'RIDIBatang',caption:'Pretendard'},
    {id:'chalk',name:'분필 칠판',channel:'HakgyoansimBunpil',title:'HakgyoansimBunpil',caption:'NotoSansKRBold'},
    {id:'brush',name:'붓글씨',channel:'NanumBrushScript',title:'NanumBrushScript',caption:'GmarketSansBold'},
    {id:'gaegu',name:'개구 손글씨',channel:'GaeguBold',title:'GaeguBold',caption:'GaeguBold'},
    {id:'danjung',name:'단정 카페',channel:'Cafe24Danjunghae',title:'Cafe24Danjunghae',caption:'Pretendard'},
    {id:'suit',name:'SUIT 모던',channel:'SUITBold',title:'SUITBold',caption:'SUITBold'},
  ];
  // 템플릿별 기본 글꼴(2026-09-19 사장님 '기본을 하나로 고정하지 말고 템플릿마다 어울리게'):
  //   폰트 템플릿을 안 골랐을 때(=템플릿 기본) 쓰는 채널명·제목·자막 글꼴. 원본 제목 글꼴의 성격을 살리고
  //   자막은 읽기 쉬운 글꼴로 짝지었다. 여기 없는 템플릿은 원본 데이터 글꼴을 그대로 쓴다.
  // 09-19 사장님: 기본은 전부 '강렬 어그로'로 고정(템플릿별로 다르게 뒀다가 되돌림).
  //   템플릿마다 다시 다르게 하려면 PRESET_FONTS에 id별로 적으면 된다 — 적힌 것이 DEFAULT_FONTS보다 우선.
  const DEFAULT_FONTS={channel:'SBAggroB',title:'SBAggroB',caption:'BlackHanSans'};
  const PRESET_FONTS={};
  window.PRESET_FONTS=PRESET_FONTS;window.DEFAULT_FONTS=DEFAULT_FONTS;   // 검사 도구가 기대 글꼴을 여기서 읽는다(한 곳에서만 정한다)
  function fontSetFamily(bind){
    const set=FONT_SETS.find(f=>f.id===fontSet)||PRESET_FONTS[rows[current]?.id]||DEFAULT_FONTS;if(!set)return '';
    return bind==='channel'?set.channel:bind==='caption'?set.caption:['hook1','hook2','bodyTitle'].includes(bind)?set.title:'';
  }
  const BODY_CAPTION_MOTIONS={
    // 09-19 사장님 '느낌이 다 비슷하다' → 이동 거리·시간·튕김을 모션마다 확실히 다르게(예전: 14px·0.3초로 거의 같았다)
    rise:{label:'스윽 올라오기',ms:380,easing:'cubic-bezier(.16,1,.3,1)',frames:[{opacity:0,transform:'translateY(70px)'},{opacity:1,transform:'translateY(0)'}]},
    grow:{label:'천천히 확대',origin:true,ms:650,easing:'cubic-bezier(.25,.8,.35,1)',frames:[{opacity:.2,transform:'scale(.45)'},{opacity:1,transform:'scale(1)'}]},
    pop:{label:'톡 튀어나오기',origin:true,ms:480,easing:'linear',frames:[{opacity:0,transform:'scale(0)'},{opacity:1,transform:'scale(1.3)',offset:.45},{transform:'scale(.92)',offset:.7},{transform:'scale(1.04)',offset:.87},{transform:'scale(1)'}]},
    slide:{label:'옆에서 밀려오기',ms:450,easing:'cubic-bezier(.2,.9,.3,1)',frames:[{opacity:0,transform:'translateX(-320px)'},{opacity:1,transform:'translateX(18px)',offset:.72},{transform:'translateX(0)'}]},
    drop:{label:'위에서 떨어지기',ms:560,easing:'linear',frames:[{opacity:0,transform:'translateY(-160px)'},{opacity:1,transform:'translateY(0)',offset:.55},{transform:'translateY(-26px)',offset:.72},{transform:'translateY(0)',offset:.86},{transform:'translateY(-6px)',offset:.93},{transform:'translateY(0)'}]},
    fade:{label:'서서히 나타나기',ms:700,easing:'ease-out',frames:[{opacity:0,filter:'blur(10px)'},{opacity:1,filter:'blur(0)'}]},
    wide:{label:'옆으로 펼치기',origin:true,ms:420,easing:'cubic-bezier(.2,.9,.3,1)',frames:[{opacity:0,transform:'scaleX(0)'},{opacity:1,transform:'scaleX(1.12)',offset:.7},{transform:'scaleX(1)'}]},
  };
  // 브라우저에 바로 기억시키기: '현재 설정 저장'을 누르지 않아도 고른 값이 새로고침 뒤에 남는다.
  const rememberLocal=patch=>{if(qaMode||labMode)return;try{const saved=JSON.parse(localStorage.getItem('scene_style_preset')||'null')||{};localStorage.setItem('scene_style_preset',JSON.stringify({...saved,...patch}))}catch{}};
  const bodyMotionPanel=document.createElement('section');
  bodyMotionPanel.className='hook-motion body-motion';
  bodyMotionPanel.innerHTML='<div class="hook-motion-head"><b>본문 자막 등장</b><small>본문 모든 장면에 적용</small></div><div class="hook-motion-grid"><button type="button" data-body-caption-motion="">없음</button>'+Object.entries(BODY_CAPTION_MOTIONS).map(([k,v])=>`<button type="button" data-body-caption-motion="${k}">${v.label}</button>`).join('')+'</div>';
  motionPanel.after(bodyMotionPanel);
  bodyMotionPanel.addEventListener('click',event=>{
    const b=event.target.closest('[data-body-caption-motion]');if(!b)return;
    bodyCaptionMotion=b.dataset.bodyCaptionMotion;syncHookMotionUI();rememberLocal({bodyCaptionMotion});if(sceneIndex===0)showScene(1);else runCaptionEnter();
  });
  const fixedPanel=document.createElement('section');
  fixedPanel.className='fixed-quick-panel';
  fixedPanel.innerHTML='<div class="fixed-quick-head"><b>고정형 빠른 조절</b><button type="button" data-fixed-reset>전체 초기화</button></div><div class="fixed-size-control" data-fixed-size="top"><span>상단 제목칸</span><button type="button" data-fixed-step="-1">−</button><input type="range" min="12" max="50" step="1" data-fixed-range="top"><output>0%</output><button type="button" data-fixed-step="1">＋</button></div><div class="fixed-size-control" data-fixed-size="bottom"><span>하단 자막칸</span><button type="button" data-fixed-step="-1">−</button><input type="range" min="0" max="35" step="1" data-fixed-range="bottom"><output>0%</output><button type="button" data-fixed-step="1">＋</button></div><div class="fixed-palette-row"><button type="button" data-fixed-palette="original">원본</button><button type="button" data-fixed-palette="mint">민트</button><button type="button" data-fixed-palette="yellow">옐로</button><button type="button" data-fixed-palette="pink">핑크</button></div><div class="fixed-color-grid"><label><span>제목 배경</span><input type="color" data-fixed-color="top"></label><label><span>하단 배경</span><input type="color" data-fixed-color="bottom"></label><label><span>제목 1</span><input type="color" data-fixed-color="title1"></label><label><span>제목 2</span><input type="color" data-fixed-color="title2"></label></div>';
  bodyMotionPanel.after(fixedPanel);
  const channelColorLabel=document.createElement('label');channelColorLabel.innerHTML='<span>채널명</span><input type="color" data-fixed-color="channel">';fixedPanel.querySelector('.fixed-color-grid').append(channelColorLabel);
  const fixedPalettes={mint:{top:'#082923',bottom:'#082923',title1:'#FFFFFF',title2:'#43E2B4'},yellow:{top:'#17140A',bottom:'#17140A',title1:'#FFFFFF',title2:'#FFE24A'},pink:{top:'#24101A',bottom:'#24101A',title1:'#FFFFFF',title2:'#FF78B7'}};
  function syncHookMotionUI(){
    motionPanel.hidden=sceneIndex>0;   // 09-19 사장님: 본문 장면에선 훅 모션 숨김(훅 전용)
    bodyMotionPanel.hidden=sceneIndex===0;
    bodyMotionPanel.querySelectorAll('[data-body-caption-motion]').forEach(b=>b.classList.toggle('active',b.dataset.bodyCaptionMotion===bodyCaptionMotion));
    motionPanel.querySelectorAll('[data-hook-motion]').forEach(b=>b.classList.toggle('active',b.dataset.hookMotion===hookMotion));
    motionPanel.querySelectorAll('[data-hook-speed]').forEach(b=>b.classList.toggle('active',Number(b.dataset.hookSpeed)===hookMotionSpeed));
    if(hookMotion==='rise'){hookMotion='zoom-punch';hookBandMotion='rise';}   // 잠깐 있던 단독 'rise' 저장값은 조합형으로 옮긴다
    motionPanel.querySelectorAll('[data-hook-band-motion]').forEach(b=>b.classList.toggle('active',b.dataset.hookBandMotion===hookBandMotion));
    const bandLabel=motionPanel.querySelector('.hook-band-motion > span');if(bandLabel)bandLabel.textContent=mode==='continuous'?'자막 등장':'흰 띠';
    motionPanel.querySelector('.hook-motion-head small').textContent=(hookMotion==='zoom-punch'?'화면 전체 확대 · 짧은 흔들림':hookMotion==='push-in'?'화면 전체가 천천히 확대':hookMotion==='shake'?'화면 전체가 훅 내내 잘게 떨림':'제목에만 적용')+(hookBandMotion==='rise'?' + 흰 띠 스윽':hookBandMotion==='grow'?' + 흰 띠 확대':'');
  }
  const minimumFixedTop=frame=>Math.min(46,Math.max(12,Math.ceil((Math.max(0,...(frame?.lines||[]).filter(line=>line.bind!=='caption').map(line=>line.y1))+2)/(frame?.height||1)*100)));
  // 썰쇼핑형은 글자를 안 줄이므로 원래 칸의 85%보다 좁히면 줄끼리 겹친다.
  const minimumStoryTop=frame=>Math.max(8,Math.ceil(captionSource(frame).cut/frame.height*100*.85));
  function syncMediaLayout(){
    if(noTemplate){Object.assign(media.style,{top:'0%',height:'100%'});return;}
    const p=rows[current],frame=frameFor(p),bounds=mediaBounds(frame,p?.id);
    Object.assign(media.style,{top:bounds.top+'%',height:bounds.height+'%'});
  }
  function syncFixedPanel(){
    fixedPanel.hidden=false;
    fixedPanel.querySelector('[data-fixed-size="bottom"] span').textContent='하단 칸';
    fixedPanel.querySelector('.fixed-quick-head b').textContent=mode==='continuous'?'고정형 빠른 조절':`${kind==='hook'?'훅':'본문'} 빠른 조절`;
    const p=rows[current],frame=frameFor(p),layout={...fixedLayoutFor(p.id,frame),top:titleHeight(frame)},colors=fixedColorsFor(p.id,frame);
    fixedPanel.querySelectorAll('[data-fixed-size]').forEach(row=>{
      const key=row.dataset.fixedSize,input=row.querySelector('input'),output=row.querySelector('output');
      if(key==='top')input.min=String(mode==='continuous'?minimumFixedTop(frame):minimumStoryTop(frame));
      input.value=String(layout[key]);output.textContent=Math.round(layout[key])+'%';
    });
    fixedPanel.querySelectorAll('[data-fixed-color]').forEach(input=>input.value=colors[input.dataset.fixedColor]);
  }
  const punchFrames=[{at:0,zoom:1,dx:0,dy:0},{at:.25,zoom:1.105,dx:0,dy:0},{at:.40,zoom:1.085,dx:-.007,dy:.002},{at:.53,zoom:1.065,dx:.006,dy:-.002},{at:.66,zoom:1.045,dx:-.003,dy:.001},{at:1,zoom:1,dx:0,dy:0}];
  // 화면 전체(카메라) 모션 — 편집기 미리보기와 최종 렌더(FFmpeg)가 같은 이 숫자를 쓴다.
  //   push-in·shake는 2026-09-18 사장님이 보낸 레퍼런스 실측값:
  //   63wyUy6d0Jc 제목 폭 125→180px/1.2초(화면 전체가 천천히 확대, 흔들림 없음)
  //   ZaPpvrHkZ1U 크기 고정·매 프레임 가로 ±2px/세로 ±3px(360px 기준) 떨림, 훅 내내
  const CAMERA_MOTIONS=['zoom-punch','push-in','shake'];
  const hookEndMs=()=>{const hs=(sceneContext?.scenes||[]).filter(s=>s.kind==='hook');return hs.length?Math.max(...hs.map(s=>s.end))*1000:2000;};
  function cameraAt(ms){
    if(hookMotion==='push-in'){
      if(ms>=hookEndMs())return {zoom:1,dx:0,dy:0};   // 훅이 끝나면 본문은 원래 크기(레퍼런스도 전환 순간 복귀)
      const dur=Math.round(1500*hookMotionSpeed/.72);   // 기본(빠름)=1.5초, 느림≈2.8초
      const t=Math.max(0,Math.min(1,ms/dur)),e=1-Math.pow(1-t,2);   // 처음 빠르고 끝에서 부드럽게 멈춤
      return {zoom:1+.32*e,dx:0,dy:0};
    }
    if(hookMotion==='shake'){
      if(ms>=hookEndMs())return {zoom:1,dx:0,dy:0};
      const f=Math.floor(ms/33.333),r=n=>{const x=Math.sin((f+1)*n)*43758.5453;return (x-Math.floor(x))*2-1;};
      const amp=.72/hookMotionSpeed;   // 빠름=기본 세기, 느림일수록 약하게
      return {zoom:1.03,dx:r(12.9898)*.0058*amp,dy:r(78.233)*.0047*amp};   // 3% 확대로 가장자리 빈틈 가림
    }
    if(hookMotion!=='zoom-punch')return {zoom:1,dx:0,dy:0};
    const t=Math.max(0,Math.min(1,ms/Math.round(760*hookMotionSpeed)));
    const i=Math.max(1,punchFrames.findIndex(f=>f.at>=t)),a=punchFrames[i-1],b=punchFrames[i],p=(t-a.at)/(b.at-a.at);
    return {zoom:a.zoom+(b.zoom-a.zoom)*p,dx:a.dx+(b.dx-a.dx)*p,dy:a.dy+(b.dy-a.dy)*p};
  }
  function cameraLayer(){
    let camera=preview.querySelector('.scene-camera');if(!camera){camera=document.createElement('div');camera.className='scene-camera';Object.assign(camera.style,{position:'absolute',inset:'0',transformOrigin:'center'});preview.prepend(camera);}
    [...preview.children].filter(el=>el!==camera&&!el.classList.contains('scene-decoration-toolbar')).forEach(el=>camera.append(el));return camera;
  }
  function runHookMotion(options){
    const seeking=options&&typeof options==='object'&&Number.isFinite(options.time);
    const camera=cameraLayer();camera.getAnimations().forEach(a=>a.cancel());camera.style.transform='none';
    if(!seeking&&(qaMode||sceneIndex!==0||matchMedia('(prefers-reduced-motion: reduce)').matches))return 0;
    // 글자뿐 아니라 상자(patch)도 지운다 — '스윽 올라오기'가 흰 띠 상자를 같이 움직이는데, 렌더는 프레임마다
    //   다시 seek하므로 안 지우면 멈춘 옛 애니메이션이 상자에 쌓인다.
    layer.querySelectorAll('.precision-text,.precision-patch').forEach(el=>el.getAnimations?.().forEach(animation=>animation.cancel()));
    // 흰 띠 스윽이 켜져 있으면 흰 띠 글자(bodyTitle)는 스윽이 맡는다 — 제목 모션까지 걸면 글자만 옆으로 튀고 상자와 갈라진다.
    const texts=[...layer.querySelectorAll('.precision-text')].filter(el=>['hook1','hook2',...(hookBandMotion?[]:['bodyTitle'])].includes(el.dataset.editBind));
    let duration=0;
    const timing={duration:620,easing:'cubic-bezier(.18,.88,.25,1)',fill:'both'};
    const time=value=>Math.round(value*hookMotionSpeed);
    const play=(element,keyframes,timing)=>{
      if(element===preview)return;
      const base=element.style.transform==='none'?'':element.style.transform;
      keyframes=keyframes.map(k=>({...k,transform:(k.transform||'')+' '+base}));
      const animation=element.animate(keyframes,timing);duration=Math.max(duration,(timing.duration||0)+(timing.delay||0));
      if(seeking){animation.pause();animation.currentTime=options.time;}
      else animation.finished.then(()=>animation.cancel()).catch(()=>{});
      return animation;
    };
    // 흰 띠 스윽 올라오기는 어느 모션과도 겹쳐 쓸 수 있다(2026-09-18 사장님 "줌펀치+스윽 조합").
    //   줌 펀치=화면 전체(카메라), 스윽=흰 띠 한 덩어리라 서로 다른 층을 움직인다.
    // 흰 띠 효과는 어느 화면 모션과도 겹쳐 쓴다(2026-09-18 사장님 "줌펀치+스윽 조합", "흰 띠도 천천히 확대").
    //   흰 띠 = 글자(bodyTitle) + 뒤의 상자(patch). 상자는 이름표가 없어 '글자를 세로로 감싸고 높이가
    //   글자의 2.2배 이하'로 짝을 찾는다(더 큰 patch는 제목판 배경이라 같이 움직이면 틀이 흔들린다).
    if(hookBandMotion){
      const band=[...layer.querySelectorAll('.precision-text')].find(el=>el.dataset.editBind==='bodyTitle');
      if(band){
        const T=band.getBoundingClientRect();
        const box=[...layer.querySelectorAll('.precision-patch')].filter(el=>{const r=el.getBoundingClientRect();
          return r.width>0&&r.top<=T.top+2&&r.bottom>=T.bottom-2&&r.height<=T.height*2.2;});
        if(hookBandMotion==='grow'){
          // 천천히 확대: 흰 띠 한 덩어리를 띠 가운데를 기준으로 1→1.12배. 글자와 상자가 같은 점을 기준으로 커져야
          //   간격이 벌어지지 않으므로 각자의 기준점을 '글자 가운데'로 맞춘다.
          const cx=T.left+T.width/2,cy=T.top+T.height/2;
          [band,...box].forEach(el=>{const r=el.getBoundingClientRect();el.style.transformOrigin=`${cx-r.left}px ${cy-r.top}px`;});
          const growTiming={duration:Math.round(1500*hookMotionSpeed/.72),easing:'cubic-bezier(.25,.1,.25,1)',fill:'both'};
          // 긴 문구는 1.12배면 화면 양끝에 닿는다(실측: 활용정점) — 실제 글자 폭 기준으로 화면 안 97%까지만 키운다.
          const range=document.createRange();range.selectNodeContents(band);const textW=range.getBoundingClientRect().width||T.width;
          // 2026-09-18 사장님 "좀 더 앞으로 많이 나오게, 너무 약하다" → 1.12→1.35배 + 상자 그림자가 짙어져 떠오르는 입체감.
          const screenW=preview.getBoundingClientRect().width,maxScale=Math.max(1,Math.min(1.35,screenW*.99/textW));
          //   긴 문구(20자+)는 화면 폭 제한으로 끝 배율이 1.1배 안팎에서 멈춘다(실측 20종 중 18종) → 0.82배에서 출발해
          //   커지는 폭 자체를 키운다(보이는 변화 1.33~1.6배). 끝 크기는 그대로라 글자는 화면 밖으로 안 나간다.
          play(band,[{transform:'scale(.82)'},{transform:`scale(${maxScale.toFixed(4)})`}],growTiming);
          box.forEach(el=>play(el,[{transform:'scale(.82)',filter:'drop-shadow(0 0 0 rgba(0,0,0,0))'},
            {transform:`scale(${maxScale.toFixed(4)})`,filter:'drop-shadow(0 10px 14px rgba(0,0,0,.55))'}],growTiming));
        }else{
          const riseTiming={duration:time(1500),easing:'cubic-bezier(.33,.3,.25,1)',fill:'both'};   // 천천히: 앞쪽 가속을 줄인 곡선
          [band,...box].forEach(el=>play(el,[{opacity:0,transform:'translateY(38px)'},{opacity:1,transform:'translateY(0)'}],riseTiming));
        }
      }
    }
    if(CAMERA_MOTIONS.includes(hookMotion)){
      // 렌더(sceneStyleExporting)는 카메라를 PNG에 굽지 않는다 — FFmpeg가 cameraAt 숫자로 따로 건다(중복 확대 방지).
      const total=hookMotion==='zoom-punch'?time(760):hookMotion==='push-in'?Math.round(1500*hookMotionSpeed/.72):Math.round(hookEndMs());
      if(!window.sceneStyleExporting){
        const steps=Math.max(2,Math.ceil(total/33.333)),frames=[];
        for(let i=0;i<=steps;i++){const c=cameraAt(i/steps*total);frames.push({offset:i/steps,transform:`translate(${c.dx*100}%,${c.dy*100}%) scale(${c.zoom})`});}
        const animation=camera.animate(frames,{duration:total,easing:'linear',fill:'forwards'});
        if(seeking){animation.pause();animation.currentTime=options.time;}else animation.finished.then(()=>animation.cancel()).catch(()=>{});
      }
      return Math.max(total,duration);
    }else if(hookMotion==='pop'){
      texts.forEach((el,index)=>play(el,[{opacity:0,transform:'scale(.25)'},{opacity:1,transform:'scale(1.14)',offset:.68},{opacity:1,transform:'scale(1)'}],{...timing,duration:time(520),delay:time(index*90)}));
    }else if(hookMotion==='slide'){
      play(preview,[{transform:'translateX(10px) scale(1.025)'},{transform:'translateX(0) scale(1)'}],{...timing,duration:time(620)});
      texts.forEach((el,index)=>play(el,[{opacity:0,transform:`translateX(${index%2?-46:46}px)`},{opacity:1,transform:'translateX(0)'}],{...timing,duration:time(620),delay:time(index*85)}));
    }else{
      play(preview,[{filter:'brightness(1)'},{filter:'brightness(1.85)',offset:.12},{filter:'brightness(.82)',offset:.25},{filter:'brightness(1)'}],{duration:time(480),easing:'ease-out'});
      texts.forEach((el,index)=>play(el,[{opacity:0,transform:'scale(1.32)',filter:'brightness(2)'},{opacity:1,transform:'scale(.96)',filter:'brightness(1.7)',offset:.3},{opacity:1,transform:'scale(1)',filter:'brightness(1)'}],{...timing,duration:time(480),delay:time(70+index*55)}));
    }
    return duration;
  }
  // 고정형 자막 등장 효과(2026-09-18) — 고정형은 훅이 없고 자막이 1~1.5초마다 바뀐다. 훅용 1.5초 효과를 그대로 걸면
  //   자리 잡기 전에 다음 자막이 와 계속 흔들리므로, 자막이 바뀔 때마다 0.3초만 짧게 들어온다.
  //   고르는 곳은 흰 띠 줄(스윽/확대)과 같다 — 자막 글자 + 자막 가림막 상자를 한 덩어리로 움직인다.
  const CAPTION_ENTER_MS=300;
  function captionMotionNow(){
    if(sceneIndex>0&&BODY_CAPTION_MOTIONS[bodyCaptionMotion])return BODY_CAPTION_MOTIONS[bodyCaptionMotion];
    if(mode==='continuous'&&hookBandMotion)return BODY_CAPTION_MOTIONS[hookBandMotion]||null;   // 고정형은 예전부터 흰 띠 줄 값이 자막 등장
    return null;
  }
  function runCaptionEnter(options){
    const seeking=options&&typeof options==='object'&&Number.isFinite(options.time);
    const motion=captionMotionNow();if(!motion)return 0;
    const text=layer.querySelector('.precision-text[data-edit-bind="caption"]'),mask=layer.querySelector('.caption-mask');
    if(!text||text.hidden||!text.textContent.trim())return 0;
    [text,mask].filter(Boolean).forEach(el=>el.getAnimations().forEach(a=>a.cancel()));const els=[text];   // 09-19: 상자는 두고 글자만 움직인다 — 상자가 움직이면 뒤 검은 칸이 드러났다
    
    if(!seeking&&(qaMode||matchMedia('(prefers-reduced-motion: reduce)').matches))return 0;
    const T=text.getBoundingClientRect(),cx=T.left+T.width/2,cy=T.top+T.height/2,ms=motion.ms||CAPTION_ENTER_MS;
    els.forEach(el=>{
      if(motion.origin){const r=el.getBoundingClientRect();el.style.transformOrigin=`${cx-r.left}px ${cy-r.top}px`;}
      const animation=el.animate(motion.frames,{duration:ms,easing:motion.easing||'cubic-bezier(.2,.8,.3,1)',fill:'both'});
      if(seeking){animation.pause();animation.currentTime=options.time;}else animation.finished.then(()=>animation.cancel()).catch(()=>{});
    });
    return ms;
  }
  function sceneTotal(){return sceneContext?.scenes?.length||12}
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
    const settings=captionSettings();
    root.querySelectorAll('[data-caption-placement]').forEach(b=>b.classList.toggle('active',b.dataset.captionPlacement===settings.placement));
    root.querySelectorAll('[data-caption-layout]').forEach(input=>{const val=settings[input.dataset.captionLayout];input.value=input.type==='color'&&!/^#[0-9a-f]{6}$/i.test(val)?'#ffffff':val;});
    const width=root.querySelector('[data-caption-layout="w"]');if(width)width.closest('label').hidden=settings.placement==='title';
    const guide=root.querySelector('.layout-a .caption-guide');
    if(guide)guide.textContent=settings.placement==='free'?'화면의 자막을 끌어 원하는 곳에 놓으세요.':'';
    captionField?.classList.remove('reserved-caption');
  }
  function presetValue(bind){
    const p=rows[current];
    return bind==='channel'?(p.sample.channel||'숏템메이커'):p.sample[bind];
  }
  function updateCount(input){
    const limit=Number(input.dataset.max)||Infinity;
    const length=[...input.value].length;
    const counter=input.closest('.field')?.querySelector('[data-count]');
    if(counter)counter.textContent=`${length}/${input.dataset.max}`;
    input.classList.toggle('contract-invalid',length>limit);
    input.setAttribute('aria-invalid',length>limit?'true':'false');
  }
  const evenLimits={channel:12,hook1:11,hook2:10,bodyTitle:22,caption:22};   // 둘째 줄 10자: 11자면 화면 양끝을 넘어 잘린다(2026-09-18 실측)
  function syncFieldLimits(){
    const limits=rows[current]?.id==='t11'?evenLimits:{channel:12,hook1:18,hook2:18,bodyTitle:22,caption:24};
    for(const [bind,input] of Object.entries(inputs)){
      input.dataset.max=String(limits[bind]||24);
      updateCount(input);
    }
  }
  function templateViolations(){
    if(rows[current]?.id!=='t11')return [];
    const labels={channel:'채널명',hook1:'훅 제목 1',hook2:'훅 제목 2',bodyTitle:'보조·본문 제목',caption:'본문 자막'};
    const found=[];
    for(const [bind,limit] of Object.entries(evenLimits)){
      const text=inputs[bind]?.value||'';
      if((bind==='hook1'||bind==='hook2')&&!text.trim())found.push(`${labels[bind]}이 비어 있습니다.`);
      if([...text].length>limit)found.push(`${labels[bind]}은 공백 포함 ${limit}자 이하여야 합니다.`);
      if((bind==='hook1'||bind==='hook2')&&/[\r\n]/.test(text))found.push(`${labels[bind]}은 한 줄이어야 합니다.`);
    }
    return found;
  }
  function resetField(bind){
    const input=inputs[bind];if(!input)return;
    input.value=presetValue(bind)||'';fontScales.delete(scaleKey(bind));textOffsets.delete(scaleKey(bind));textDrags.delete(scaleKey(bind));   // 09-19: 마우스로 옮긴 자리도 되돌린다
    [...fittedText.keys()].filter(key=>key.startsWith(scaleKey(bind)+':')).forEach(key=>fittedText.delete(key));
    if(bind==='caption'){captionLayouts.delete(captionKey());captionPositions.delete(captionKey());captionDrags.delete(captionKey());captionTexts.delete(captionKey());syncCaption();}
    markDirty(bind);updateCount(input);updateSteppers();updateCaptionButtons();renderEdit();
  }

  function frameKeys(frameKind,p){
    if(p.mode==='continuous')return [...(p.frame.channel_boxes?.length?['channel']:[]),...new Set((p.frame.lines||[]).map(line=>line.bind).filter(Boolean))];
    const frame=p[frameKind];
    const hasChannel=!!(frame?.channel_box||frame?.channel_boxes?.length);
    const lineCount=frame?.lines?.length||0;
    return p.id==='s0101'
      ? (frameKind==='hook'?['channel','hook1','hook2',...(((p.hook?.lines?.length||0)>2||p.hook?.white_box?.text)?['bodyTitle']:[])]:['channel','bodyTitle','caption'])
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
    syncFieldLimits();
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
    const manualLines=bind==='caption'?String(text).split('\n').length:1;
    if(manualLines>1)ln={...ln,max_lines:manualLines,h:ln.h*manualLines,y0:ln.y0-ln.h*(manualLines-1)/2};
    const scale=preview.clientHeight/frame.height;
    const measuredBounds=role.includes('left')||role.includes('precision-channel');
    const pad=measuredBounds?Math.max(2,Math.round(4*scale)):0;
    const el=document.createElement('div');el.className='precision-text '+role;el.dataset.editBind=bind;
    const left=measuredBounds?Math.max(0,ln.x0/frame.width*100-1.6):Math.max(1.5,(ln.x0||0)/frame.width*100);
    const right=measuredBounds?Math.max(0,(frame.width-1-ln.x1)/frame.width*100-1.6):Math.max(1.5,(frame.width-1-(ln.x1??frame.width-1))/frame.width*100);
    const fontPx=ln.font_size?ln.font_size*scale:ln.h*scale*1.05;
    // 기본 외곽선/그림자는 제거하고 색 대비 부족 시에만 아래에서 얇게 보정한다.
    const stroke=0,shadowY=0;
    const pickedFont=fontSetFamily(bind);
    const family=pickedFont||ln.font_family||frame.font_family||'TmonMonsori';
    const weight=pickedFont?400:(ln.font_weight||frame.font_weight||400);   // 세트 폰트는 한 굵기뿐 — 가짜 볼드 방지
    const letterPx=ln.letter_spacing!=null?ln.letter_spacing*scale:Math.max(-1.5,-.035*fontPx);
    const capped=bind==='channel'&&pickedFont?Math.min(fontPx,frame.height*scale*CHANNEL_MAX):fontPx;   // 09-19: 채널명 기본 크기 상한
    const manualScale=textScale(bind),scaledFont=Math.max(9,capped*manualScale);
    const moved=textDrags.get(scaleKey(bind))||{x:0,y:0};   // 09-19 사장님: 제목·채널명도 마우스로 옮긴다
    const topOffset=(bind==='caption'?captionOffset()+fixedCaptionShift(frame):0)+textOffset(bind)+(bind==='caption'?0:moved.y);
    const verticalNudge=bind==='channel'?.7:-.35;
    const baseHeight=ln.h/frame.height*100+.9,displayHeight=baseHeight*Math.max(1,manualScale);
    const displayTop=ln.y0/frame.height*100+verticalNudge+topOffset-(displayHeight-baseHeight)/2;
    const shiftX=bind==='caption'?0:moved.x;
    Object.assign(el.style,{left:(left+shiftX)+'%',right:(right-shiftX)+'%',top:Math.max(0,displayTop)+'%',height:displayHeight+'%',fontSize:scaledFont+'px',fontFamily:`"${family}",sans-serif`,fontWeight:String(weight),fontStyle:ln.font_style||'normal',letterSpacing:letterPx+'px',color:rgba(color||ln.color||'#fff'),textShadow:shadowY?`0 ${shadowY}px 1px rgba(0,0,0,.88)`:'none',webkitTextStroke:stroke?`${stroke}px #080808`:'0',padding:`0 ${pad}px`,whiteSpace:ln.max_lines>1?'normal':'nowrap',flexWrap:ln.max_lines>1?'wrap':'nowrap',alignContent:ln.max_lines>1?'center':'normal',lineHeight:ln.max_lines>1?'1.05':'1'});
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
    if(manualLines>1){el.textContent=text;el.style.whiteSpace='pre-wrap';el.style.display='block';el.style.lineHeight='1.2';el.style.textWrap='wrap';}
    else if(ln.max_lines>1||WRAP3.includes(bind)){el.style.whiteSpace='normal';el.style.overflowWrap='anywhere';el.style.wordBreak='keep-all';el.style.textWrap='balance';el.style.lineHeight='1.18';el.style.display='-webkit-box';el.style.webkitBoxOrient='vertical';el.style.webkitLineClamp='3';}   // 09-19 사장님: 본문 제목·자막은 3줄까지
    const chosen=colorOverrides.get(colorKey(bind==='hook2'?'accent':'white'));
    if(chosen){el.style.color=chosen;el.querySelectorAll('span').forEach(span=>span.style.color=chosen);}
    layer.insertBefore(el,badge);
    if(bind==='caption'){el.style.left=(left+captionX())+'%';el.style.right=(right-captionX())+'%';}
    // 이븐쇼핑 기준형은 원본 폰트 크기·자간·가로비를 잠근다. 긴 문구를 몰래
    // 축소하거나 찌그러뜨리지 않고 templateViolations가 적용 전에 되돌려 보낸다.
    const lockedReference=rows[current]?.id==='t11'&&frame.reference_style&&!pickedFont;   // 09-19: 글꼴을 바꾸면 원본 크기 잠금을 풀어야 글자가 안 잘린다
    if(!lockedReference){
      const fitKey=`${scaleKey(bind)}:${family}:${weight}:${ln.x0}:${Math.round(el.clientWidth)}`   /* 09-19: 세로 위치(y0)는 글자 폭과 무관 — 칸을 올리고 내릴 때마다 다시 맞춰 크기가 0.5~1.5px 튀었다 */,chars=Math.max(1,[...String(text||' ')].length),cached=fittedText.get(fitKey);
      let useCache=cached&&chars<=cached.capacity;
      if(useCache){el.style.fontSize=cached.size+'px';if(cached.letter!=null)el.style.letterSpacing=cached.letter+'px';const xscale=cached.xscale??1;if(xscale<1){el.style.transform=`scaleX(${xscale})`;el.style.transformOrigin=role.includes('left')?'left center':'center';}
        // 09-19: 기억해 둔 크기를 그대로 쓰면 글꼴이 바뀐 뒤 글자가 칸 밖으로 나갔다(본문 제목 좌우 잘림). 넘치면 캐시를 버리고 다시 맞춘다.
        const probe=document.createRange();probe.selectNodeContents(el);
        if(Math.max(el.scrollWidth,probe.getBoundingClientRect().width)*xscale>el.clientWidth+1){useCache=false;fittedText.delete(fitKey);el.style.transform='none';el.style.letterSpacing='';}
      }
      if(!useCache){const isStory=mode==='story',manualSize=fontScales.has(scaleKey(bind));const heightFit=!(rows[current]?.id==='t11'&&frame.reference_style);   // 09-19: 이븐쇼핑은 칸 높이를 바꿔도 글자 크기는 그대로(폭만 맞춘다)
        if(!manualSize)fitText(el,scaledFont,isStory ? .3 : .12,heightFit);const fitted=parseFloat(el.style.fontSize)||scaledFont;el.style.fontSize=fitted+'px';let fittedLetter=parseFloat(getComputedStyle(el).letterSpacing)||0;const range=document.createRange();range.selectNodeContents(el);const measuredWidth=()=>Math.max(el.scrollWidth,range.getBoundingClientRect().width);const minLetter=isStory?-fitted*.08:-fitted*.3;while(!manualSize&&measuredWidth()>el.clientWidth+2&&fittedLetter>minLetter){fittedLetter-=.2;el.style.letterSpacing=Math.max(minLetter,fittedLetter)+'px';}const overflowScale=el.clientWidth/Math.max(1,measuredWidth())*.98;const xscale=manualSize?1:isStory?Math.min(1,overflowScale):Math.min(Number(ln.scale_x)||1,overflowScale);if(xscale<1){el.style.transform=`scaleX(${xscale})`;el.style.transformOrigin=role.includes('left')?'left center':'center';}fittedText.set(fitKey,{capacity:chars+1,size:fitted,letter:fittedLetter,xscale});}
    }
    return el;
  }
  function setNoTemplate(){
    noTemplate=true;document.body.classList.add('no-template');
    grid.querySelectorAll('[data-p20]').forEach(x=>x.classList.remove('selected'));grid.querySelector('[data-none]')?.classList.add('selected');
    renderEdit();
  }
  function renderEdit(){
    // 글자층을 비워야 scene-style-connect의 감시(MutationObserver)가 돌아 영상 틀을 화면 전체로 다시 잡는다.
    if(noTemplate){[...layer.children].filter(x=>x!==badge).forEach(x=>x.remove());layer.hidden=true;Object.assign(media.style,{top:'0%',height:'100%'});return;}
    [...layer.children].filter(x=>x!==badge).forEach(x=>x.remove());
    const p=rows[current],frame=frameFor(p);if(!frame)return;
    sourceClean.replaceChildren();
    for(const region of frame.cleanup_regions||[]){if(region.role!=='original-title')continue;const cover=document.createElement('div');Object.assign(cover.style,{position:'absolute',left:(region.x||0)/frame.width*100+'%',top:region.y/frame.height*100+'%',width:(region.width||frame.width)/frame.width*100+'%',height:region.height/frame.height*100+'%',background:region.background||frame.title_bg||'#111111'});sourceClean.append(cover);}
    // Reference screenshots are picker assets, never a live editable background.
    // Their baked-in letters/icons cannot follow resized title geometry.
    base.hidden=true;sourceClean.hidden=true;
    const mediaSource=sceneContext?.scenes?.[sceneIndex]?.media||frame.media_source||uniformMedia;if(media.getAttribute('src')!==mediaSource)media.src=mediaSource;
    badge.textContent=frame.design_label?frame.design_label:'원본 실측 편집';
    badge.hidden=!!frame.design_label;
    const dirty=currentDirty();
    const bg=frame.title_bg||frame.top_band?.color||'#111111';
    const fixedLayout=mode==='continuous'?fixedLayoutFor(p.id,frame):null;
    const fixedPaint=mode==='continuous'?fixedColorsFor(p.id,frame):null;
    if(mode==='story'&&!frame.design_label){
      addPatch(0,captionSource(frame).cut/frame.height*100,bg);
      if(frame.top_band)addPatch(frame.top_band.y0/frame.height*100,(frame.top_band.y1-frame.top_band.y0+1)/frame.height*100,frame.top_band.color);
    }
    (frame.cleanup_regions||[]).forEach(region=>{
      if(region.role==='source-footer'||(mode==='continuous'&&region.role==='original-title'))return;
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
      if(s.bind==='caption')return;
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
      if(key==='caption'||!dirty.has(key))return;
      const drawLine=storyBodyLine(fixedDrawLine(ln,frame),frame),pt=drawLine.patch_top??2,pb=drawLine.patch_bottom??2;
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
    if(wb&&kind==='hook'){
      // 원본 설명띠의 글자/흔적을 먼저 완전히 덮고 편집 가능한 텍스트만 다시 올린다.
      const movedCaption=kind==='body'&&(fixedLayouts.get(layoutKey(p.id,frame))?.bottom||0)>0;
      addPatch(wb.y0/frame.height*100,(wb.y1-wb.y0+1)/frame.height*100,movedCaption?(fixedColorsFor(p.id,frame).top||bg):(wb.background||'#FFFFFF'),0,100,'white-box');
    }
    if(wb?.text&&kind==='hook'){
      const key=kind==='hook'?'bodyTitle':'caption';
      if(dirty.has(key)){const offset=(key==='caption'?captionOffset():0)+textOffset(key);if(offset)addPatch(wb.y0/frame.height*100,(wb.y1-wb.y0+1)/frame.height*100,'#FFFFFF',0,100,key);addPatch(wb.y0/frame.height*100+offset,(wb.y1-wb.y0+1)/frame.height*100,'#FFFFFF',0,100,key);addText(value(key),wb.text,frame,'#111111','center',key);}
    }
    if(mode==='story'){
      applyStoryLayout(frame,p);
      const storyBottom=fixedLayoutFor(p.id,frame).bottom;
      if(storyBottom>0)addPatch(100-storyBottom,storyBottom,fixedColorsFor(p.id,frame).bottom,0,100,'bottom-band');
    }
    const paint=fixedColors.get(layoutKey(p.id,frame));
    if(paint){
      const channelColor=fixedColorsFor(p.id,frame).channel;
      layer.querySelectorAll('.precision-text[data-edit-bind="channel"]').forEach(el=>{el.style.color=channelColor;el.querySelectorAll('span').forEach(span=>span.style.color=channelColor);});
      if(paint.top)layer.querySelectorAll('.body-ornament').forEach(el=>el.style.color=readableInk(paint.top));
      // 채널명 칸도 제목 배경색을 따른다 — 안 그러면 빠른 조절 색을 바꿔도 채널명 뒤만 원래 검정으로 남는다(2026-09-18 사장님 제보).
      if(paint.top)layer.querySelectorAll('[data-edit-bind="channel"]').forEach(el=>{if(el.style.background||el.style.backgroundColor)el.style.background=paint.top;});
    }
    if(hasEditableCaption())renderCaption(frame);
    syncMediaLayout();
  }
  function applyStoryLayout(frame,p){
    // 이븐쇼핑 원본형은 측정 좌표 자체가 계약이다. 장면별 자막칸 보정으로
    // 제목 영역이나 글자 크기를 다시 압축하면 훅/본문이 서로 흔들린다.
    const source=captionSource(frame),cut=source.cut/frame.height*100,next=titleHeight(frame),paint=fixedColors.get(layoutKey(p.id,frame));
    // 이븐쇼핑 원본형은 측정 좌표 자체가 계약 — 제목칸을 안 건드렸으면 그대로 둔다.
    const moved=Math.abs(next-cut)>.05;
    if(p.id==='t11'&&frame.reference_style&&!moved)return;
    // 상단 제목칸 조절 = 칸만 커지고 줄어든다(2026-09-18 사장님 "칸만 줄어들어야 하는데 글자도 비율로 줄어들면 안 좋다",
    //   "50%로 키우면 흰 띠 아래가 까맣게 빈다"). 글자·띠 크기는 그대로 두고 **위치만** 칸 안에 고르게 벌린다:
    //   맨 위(채널명)는 거의 제자리, 맨 아래(흰 띠)는 칸 바닥을 따라가고, 가운데는 그 사이 비율만큼.
    //   칸 전체를 채우는 배경판만 새 높이로 늘린다.
    for(const el of [...layer.children].filter(el=>el!==badge)){
      const top=parseFloat(el.style.top),height=parseFloat(el.style.height);if(!Number.isFinite(top))continue;
      if(top>=cut&&hasEditableCaption()){if(el.classList.contains('precision-text')&&['channel','hook1','hook2','bodyTitle'].includes(el.dataset.editBind))continue;el.remove();continue;}   // 09-19: 끌어 옮긴 제목·채널명은 지우지 않는다(사라지던 문제)
      if(moved){
        const h=Number.isFinite(height)?Math.min(height,cut-top):(el.getBoundingClientRect().height/Math.max(1,preview.clientHeight)*100);
        if(top<=.5&&Number.isFinite(height)&&height>=cut*.8){el.style.height=next+'%';}
        else{
          const f=Math.max(0,Math.min(1,(top+h)/Math.max(.01,cut)));   // 아래 끝 기준 — 흰 띠가 칸 바닥에 딱 붙어 따라간다
          el.style.top=Math.max(0,Math.min(next-h,top+(next-cut)*f))+'%';
          if(Number.isFinite(height))el.style.height=Math.max(0,h)+'%';
        }
      }
      if(paint){
        if(el.classList.contains('precision-text')){
          const color=el.dataset.editBind==='hook1'?paint.title1:['hook2','bodyTitle'].includes(el.dataset.editBind)?paint.title2:null;
          if(color){el.style.color=color;el.querySelectorAll('span').forEach(s=>s.style.color=color);}
        }else if(el.style.background&&paint.top)el.style.background=paint.top;
      }
    }
    // 09-19: 본문 제목은 20종 모두 같은 자리(자막 칸 시작 대비 비율). 위 배치 보정이 끝난 뒤 마지막에 자리를 잡는다.
    if(isStoryBody(frame)){
      const el=layer.querySelector('.precision-text[data-edit-bind="bodyTitle"]');
      if(el){
        // 채널명 아래 최소 1.2% 띄운다(원본 채널 위치가 6.3~11.1%로 제각각이라 붙거나 겹쳤다)
        const chEl=layer.querySelector('.precision-text[data-edit-bind="channel"]');
        const pvBox=preview.getBoundingClientRect();
        const chMoved=textDrags.get(scaleKey('channel'))||{y:0};   // 09-19: 채널명을 옮겨도 제목은 따라오지 않게 — 옮긴 양을 빼고 원래 자리로 계산
        const chBottom=chEl?((chEl.getBoundingClientRect().bottom-pvBox.top)/pvBox.height*100)-chMoved.y:0;
        const drag=textDrags.get(scaleKey('bodyTitle'))||{x:0,y:0};
        const base=Math.max(STORY_BODY.cut*STORY_BODY.titleTop,chBottom+1.2);
        const top=Math.max(0,Math.min(95,base+drag.y));el.style.top=top+'%';   // 끌어 옮긴 만큼 반영(화면 안에서만)
        // 자막 칸을 덮지 않는 선까지만 칸을 키운다(3줄 허용). 글자를 손으로 키웠어도 칸을 넘으면 줄인다 — 넘치면 자막·영상을 가린다.
        el.style.height=Math.max(STORY_BODY.cut*STORY_BODY.titleH,STORY_BODY.cut-top-0.8)+'%';   // 09-19: 자막 칸 직전까지 제목 칸으로 쓴다(키운 글자가 도로 줄던 문제)
        let size=parseFloat(el.style.fontSize)||0;
        for(let guard=0;guard<80&&size>9&&el.scrollHeight>el.clientHeight+1;guard++){size-=.5;el.style.fontSize=size+'px';}
      }
    }
  }
  // 고정형 자막칸 디자인(2026-09-18 사장님 "이븐쇼핑 흰 띠처럼 그라데이션 있게, 다 똑같으면 밋밋하니 다르게").
  //   템플릿마다 6가지 중 하나가 고정으로 붙는다(프리셋 id로 고르므로 같은 템플릿은 늘 같은 모양).
  //   사용자가 자막칸 배경을 직접 저장했으면 그 색이 우선 — 디자인을 덮지 않는다.
  //   accent = 그 템플릿 제목 둘째 줄 색(템플릿 성격을 자막칸에도 잇는다).
  const CAPTION_LOOKS=[
    a=>({color:'#080808',box:{background:'linear-gradient(180deg,#FFFFFF,#FFFFFF 70%,#E6E8E6)',boxShadow:'0 0 12px 6px rgba(255,255,255,.55)',left:'1.2%',width:'97.6%',borderRadius:'2px'}}),   // 이븐쇼핑형 흰 띠
    a=>({color:'#FFFFFF',box:{background:'linear-gradient(180deg,#2B2B2B,#0E0E0E)',boxShadow:`inset 0 1px 0 rgba(255,255,255,.18),0 3px 10px rgba(0,0,0,.55)`,borderTop:`2px solid ${a}`}}),                    // 검정 유리 + 윗선 포인트
    a=>({color:'#111111',box:{background:`linear-gradient(90deg,${a}33,#FFFFFF 18%,#FFFFFF 82%,${a}33)`,boxShadow:'0 4px 10px rgba(0,0,0,.35)'}}),                                                          // 흰 바탕 양끝 포인트색 번짐
    a=>({color:'#FFFFFF',box:{background:`linear-gradient(180deg,${a},${a}CC)`,boxShadow:'0 4px 12px rgba(0,0,0,.45)',left:'4%',width:'92%',borderRadius:'999px'}}),                                          // 포인트색 알약
    a=>({color:'#141414',box:{background:'linear-gradient(180deg,#FFF9E8,#F3E9CF)',boxShadow:'0 5px 12px rgba(0,0,0,.4)',left:'3%',width:'94%',borderRadius:'6px'}}),                                         // 종이 카드
    a=>({color:'#FFFFFF',box:{background:'linear-gradient(90deg,rgba(0,0,0,0),rgba(0,0,0,.85) 15%,rgba(0,0,0,.85) 85%,rgba(0,0,0,0))',borderBottom:`3px solid ${a}`}}),                                   // 가운데 짙은 띠 + 밑줄 포인트
    // 2026-09-18 사장님 "그라데이션이나 고급스러운 거 몇 개 넣어줘" — 고를 수 있는 고급형 4종
    a=>({color:'#2A1B00',box:{background:'linear-gradient(180deg,#FFF3C4,#E8C46A 55%,#C99A2E)',boxShadow:'inset 0 1px 0 rgba(255,255,255,.7),0 4px 12px rgba(0,0,0,.45)',left:'3%',width:'94%',borderRadius:'6px'}}),   // 골드
    a=>({color:'#F6E7B8',box:{background:'linear-gradient(180deg,#1B2A4A,#0B1428)',boxShadow:'0 4px 12px rgba(0,0,0,.5)',borderTop:'2px solid #D9B45A',borderBottom:'2px solid #D9B45A'}}),                        // 네이비 + 금테
    a=>({color:'#FFFFFF',box:{background:'linear-gradient(180deg,rgba(255,255,255,.28),rgba(255,255,255,.10))',backdropFilter:'blur(8px)',border:'1px solid rgba(255,255,255,.45)',boxShadow:'0 4px 14px rgba(0,0,0,.35)',left:'4%',width:'92%',borderRadius:'12px'},text:{textShadow:'0 1px 3px rgba(0,0,0,.6)'}}),   // 반투명 유리
    a=>({color:'#FFFFFF',box:{background:'linear-gradient(90deg,#FF4FA3,#7B5CFF 55%,#2EC5FF)',boxShadow:'0 4px 14px rgba(123,92,255,.55)',left:'4%',width:'92%',borderRadius:'999px'}}),                            // 3색 그라데이션 알약
  ];
  const CAPTION_LOOK_NAMES=['흰 띠','검정 유리','흰 바탕 번짐','포인트 알약','종이 카드','짙은 띠','골드','네이비 금테','반투명 유리','3색 그라데이션'];
  // 자막박스 없음 — 박스 없이 흰 글자 + 검은 외곽선·그림자만(영상 위에 바로 얹힌 자막).
  const CAPTION_NONE={color:'#FFFFFF',box:{background:'transparent',boxShadow:'none',border:'0',backdropFilter:'none'},text:{textShadow:'0 0 3px #000,0 0 3px #000,0 2px 4px rgba(0,0,0,.8)',WebkitTextStroke:'0.6px #000'}};
  function captionLook(frame){
    // 사용자가 배경색을 직접 고른 때만(bgUser) 디자인을 끈다. 끌어 옮기기도 captionSettings() 전체를 저장해 background가
    //   늘 들어가 있어서, 옛 조건(background 있음)으로는 한 번 끌면 디자인이 회색 띠로 바뀌었다(2026-09-18 사장님 제보·재현).
    const saved=captionLayouts.get(captionKey())||{};
    if(saved.look==='none')return CAPTION_NONE;
    const accent0=(fixedColorsFor(rows[current].id,frame).title2||'#00F9ED').slice(0,7);
    if(Number.isInteger(saved.look)&&CAPTION_LOOKS[saved.look])return CAPTION_LOOKS[saved.look](accent0);   // 사용자가 고른 모양(썰쇼핑형 본문에도 적용)
    if(mode!=='continuous'||saved.bgUser)return null;
    const id=rows[current].id||'';let h=0;for(const ch of id)h=(h*31+ch.charCodeAt(0))>>>0;
    const accent=(fixedColorsFor(id,frame).title2||'#00F9ED').slice(0,7);
    return CAPTION_LOOKS[h%6](accent);   // 자동 배정은 원래 6종 안에서(템플릿마다 늘 같은 모양 유지)
  }
  function renderCaption(frame){
    if(!captionVisible())return;
    const settings=captionSettings(),source=captionSource(frame),drag=captionDrags.get(captionKey())||{x:0,y:0};
    const w=settings.placement==='title'?100:settings.w,h=settings.h;
    const x=settings.placement==='title'?0:Math.max(0,Math.min(100-w,(100-w)/2+drag.x));
    const y=settings.placement==='title'?titleHeight(frame):Math.max(0,Math.min(100-h,titleHeight(frame)+drag.y+textOffset('caption')));
    const patch=addPatch(y,h,settings.background,x,w,'caption');patch.classList.add('caption-mask');patch.style.background=settings.background;
    const capLook=captionLook(frame);
    if(capLook){const {left,width,...look}=capLook.box;Object.assign(patch.style,settings.placement==='title'?capLook.box:look);if(!settings.colorUser)settings.color=capLook.color;}   // 옮긴 자막은 옮긴 자리·폭 유지
    const original=source.ln||{font_size:frame.height*.032,font_family:frame.font_family||'Pretendard',font_weight:900};
    // 고정형 자막 기본 크기 = 템플릿 값의 82%(2026-09-18 사장님 "자막쪽이 너무 크다"). 이븐쇼핑 본문과 같은 3.6%였지만
    //   굵은 흰 글씨·제목과의 크기 차이가 작아 커 보였다. −/+ 조절(textScale)은 이 위에 그대로 곱해진다.
    const baseSize=(original.font_size||frame.height*.032)*(mode==='continuous'?.82:1);
    const ln={...original,font_size:baseSize,x0:(x+2)/100*frame.width,x1:(x+w-2)/100*frame.width,y0:y/100*frame.height,h:h/100*frame.height,max_lines:1,no_patch:true};
    addText(value('caption'),ln,frame,settings.color,'center','caption');
    const text=layer.querySelector('.precision-text[data-edit-bind="caption"]');
    Object.assign(text.style,{left:(x+2)+'%',right:'auto',width:Math.max(1,w-4)+'%',top:y+'%',height:h+'%',transform:'none',display:'flex',alignItems:'center',justifyContent:'center',whiteSpace:'pre-wrap',lineHeight:'1.15',color:settings.color});
    text.textContent=value('caption');text.querySelectorAll('span').forEach(s=>s.style.color=settings.color);
    if(capLook?.text)Object.assign(text.style,capLook.text);
  }
  function showFrame(next){
    kind=mode==='continuous'?'hook':next;
    if(mode!=='continuous'&&sceneContext?.scenes?.length){const index=sceneContext.scenes.findIndex(s=>s.kind===kind);if(index>=0)sceneIndex=index;else kind=sceneKind(sceneIndex);}
    else if(mode!=='continuous'&&kind==='hook')sceneIndex=0;
    else if(mode!=='continuous'&&sceneIndex===0)sceneIndex=1;
    const p=rows[current],source=imageFor(p);
    base.src=source;
    const frame=frameFor(p),bounds=mediaBounds(frame,p.id);Object.assign(media.style,{top:bounds.top+'%',height:bounds.height+'%'});
    preview.classList.toggle('is-body',mode!=='continuous'&&kind==='body');
    preview.classList.toggle('is-continuous',mode==='continuous');
    const seg=root.querySelector('.layout-a .seg');if(seg)seg.hidden=mode==='continuous';
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    syncCaption();fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();syncHookMotionUI();syncFixedPanel();requestAnimationFrame(runHookMotion);requestAnimationFrame(()=>runCaptionEnter());
  }
  function showScene(nextIndex){
    sceneIndex=Math.max(0,Math.min(sceneTotal()-1,nextIndex));
    kind=mode==='continuous'?'hook':sceneKind(sceneIndex);
    if(mode==='continuous'){
      markDirty('caption');
      inputs.caption.value=sceneIndex>0?(rows[current].sample.caption||'이런 방법이 있었네요'):'';
    }
    const p=rows[current],source=imageFor(p,sceneIndex);
    base.src=source;const frame=frameFor(p,sceneIndex),bounds=mediaBounds(frame,p.id);Object.assign(media.style,{top:bounds.top+'%',height:bounds.height+'%'});preview.classList.toggle('is-body',mode!=='continuous'&&kind==='body');
    root.querySelectorAll('.layout-a [data-frame]').forEach(x=>x.classList.toggle('active',x.dataset.frame===kind));
    syncCaption();fieldSet(kind,p);updateSceneUI();updateSteppers();updateCaptionButtons();renderEdit();syncHookMotionUI();syncFixedPanel();requestAnimationFrame(runHookMotion);requestAnimationFrame(()=>runCaptionEnter());   // 09-19: [다음]으로 넘길 때도 본문 모션이 돈다(전엔 showFrame에만 있었다)
  }
  function selectPreset(index){
    noTemplate=false;document.body.classList.remove('no-template');grid.querySelector('[data-none]')?.classList.remove('selected');
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
    if(sceneContext?.text)for(const [key,text] of Object.entries(sceneContext.text))if(inputs[key])inputs[key].value=text;
    preview.classList.remove('is-pristine');showFrame(kind);
  }
  grid.addEventListener('click',e=>{if(e.target.closest('[data-none]')){setNoTemplate();return;}const card=e.target.closest('[data-p20]');if(card)selectPreset(+card.dataset.p20)});
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
    else if(sceneContext?.text)sceneContext.text[input.dataset.bind]=input.value;
    updateCount(input);markDirty(input.dataset.bind);preview.classList.remove('is-pristine');renderEdit();
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
    if(bind==='caption'){captionLayouts.set(captionKey(),{...captionSettings(),placement:'free'});updateCaptionButtons();}
    textOffsets.set(scaleKey(bind),Math.max(-18,Math.min(18,textOffset(bind)+Number(button.dataset.positionStep)*.5)));
    if(bind==='caption')applyCaptionMoveScope();
    markDirty(bind);preview.classList.remove('is-pristine');renderEdit();
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-field-reset]');if(!button)return;
    resetField(button.closest('[data-field-key]').dataset.fieldKey);
  });
  colorRow?.addEventListener('input',event=>{
    const input=event.target.closest('[data-color-role]');if(!input)return;
    const role=input.dataset.colorRole,p=rows[current],key=layoutKey(p.id,frameFor(p)),paint={...(fixedColors.get(key)||{})};
    if(role==='background'){paint.top=input.value;paint.bottom=input.value;}
    else paint[role==='white'?'title1':'title2']=input.value;
    fixedColors.set(key,paint);colorOverrides.set(colorKey(role),input.value);preview.classList.remove('is-pristine');renderEdit();syncFixedPanel();
  });
  motionPanel.addEventListener('click',event=>{
    const choice=event.target.closest('[data-hook-motion]');
    if(choice){hookMotion=choice.dataset.hookMotion;if(sceneIndex!==0){sceneIndex=0;showFrame('hook');}syncHookMotionUI();runHookMotion();return}
    const bandChoice=event.target.closest('[data-hook-band-motion]');
    if(bandChoice&&mode==='continuous'){hookBandMotion=bandChoice.dataset.hookBandMotion;syncHookMotionUI();if(sceneIndex===0)showScene(1);else runCaptionEnter();return}
    if(bandChoice){hookBandMotion=bandChoice.dataset.hookBandMotion;if(sceneIndex!==0){sceneIndex=0;showFrame('hook');}syncHookMotionUI();runHookMotion();return}
    const speed=event.target.closest('[data-hook-speed]');
    if(speed){hookMotionSpeed=Number(speed.dataset.hookSpeed);motionPanel.querySelectorAll('[data-hook-speed]').forEach(button=>button.classList.toggle('active',button===speed));runHookMotion();return}
  });
  const applyFixedSize=(key,rawValue)=>{
    const p=rows[current],frame=frameFor(p),currentLayout={...fixedLayoutFor(p.id,frame),top:titleHeight(frame),titleOnly:true};
    const min=key==='top'?(mode==='continuous'?minimumFixedTop(frame):minimumStoryTop(frame)):0,max=key==='top'?50:35;
    currentLayout[key]=Math.round(Math.max(min,Math.min(max,Number(rawValue))));
    if(currentLayout.top+currentLayout.bottom>70)currentLayout[key]=70-currentLayout[key==='top'?'bottom':'top'];
    fixedLayouts.set(layoutKey(p.id,frame),currentLayout);fittedText.clear();preview.classList.remove('is-pristine');syncMediaLayout();renderEdit();syncFixedPanel();
  };
  fixedPanel.addEventListener('input',event=>{
    const range=event.target.closest('[data-fixed-range]');
    if(range){applyFixedSize(range.dataset.fixedRange,range.value);return}
    const color=event.target.closest('[data-fixed-color]');
    if(color){
      const p=rows[current],key=layoutKey(p.id,frameFor(p)),next={...(fixedColors.get(key)||{})};next[color.dataset.fixedColor]=color.value;fixedColors.set(key,next);
      colorOverrides.delete(colorKey(color.dataset.fixedColor==='title1'?'white':color.dataset.fixedColor==='title2'?'accent':'background'));
      preview.classList.remove('is-pristine');renderEdit();syncFixedPanel();
    }
  });
  fixedPanel.addEventListener('click',event=>{
    const step=event.target.closest('[data-fixed-step]');
    if(step){const row=step.closest('[data-fixed-size]'),key=row.dataset.fixedSize;applyFixedSize(key,Number(row.querySelector('input').value)+Number(step.dataset.fixedStep));return}
    const palette=event.target.closest('[data-fixed-palette]');
    if(palette){
      const p=rows[current],key=layoutKey(p.id,frameFor(p));
      for(const role of ['white','accent','background'])colorOverrides.delete(colorKey(role));
      if(palette.dataset.fixedPalette==='original')fixedColors.delete(key);else fixedColors.set(key,{...fixedPalettes[palette.dataset.fixedPalette]});
      preview.classList.remove('is-pristine');renderEdit();syncFixedPanel();return;
    }
    if(event.target.closest('[data-fixed-reset]')){
      const p=rows[current],key=layoutKey(p.id,frameFor(p));fixedLayouts.delete(key);fixedColors.delete(key);for(const role of ['white','accent','background'])colorOverrides.delete(colorKey(role));fittedText.clear();syncMediaLayout();renderEdit();syncFixedPanel();
    }
  });
  const saveButton=root.querySelector('.layout-a .secondary');
  saveButton?.addEventListener('click',()=>{
    const snapshot=window.sceneStyle.snapshot();
    localStorage.setItem('scene_style_preset',JSON.stringify(snapshot));saveButton.textContent='✓ 현재 설정 저장됨';setTimeout(()=>saveButton.textContent='현재 설정 저장',1400);
  });
  captionField?.addEventListener('click',event=>{
    const button=event.target.closest('[data-caption-placement]');if(!button)return;
    const settings=captionSettings();captionLayouts.set(captionKey(),{...settings,placement:button.dataset.captionPlacement});
    if(button.dataset.captionPlacement==='title'){captionDrags.delete(captionKey());textOffsets.delete(scaleKey('caption'));}
    applyCaptionMoveScope();
    markDirty('caption');updateCaptionButtons();renderEdit();
  });
  captionField?.addEventListener('input',event=>{
    const input=event.target.closest('[data-caption-layout]');if(!input)return;
    const settings=captionSettings();settings[input.dataset.captionLayout]=input.type==='range'?Number(input.value):input.value;if(input.dataset.captionLayout==='background'){settings.bgUser=true;delete settings.look;}if(input.dataset.captionLayout==='color')settings.colorUser=true;
    captionLayouts.set(captionKey(),settings);markDirty('caption');renderEdit();
  });
  root.querySelector('.layout-a .edit-pane').addEventListener('click',event=>{
    const button=event.target.closest('[data-caption-position]');if(!button)return;
    captionPositions.set(captionKey(),Number(button.dataset.captionPosition));markDirty('caption');updateCaptionButtons();renderEdit();
  });
  addEventListener('resize',()=>{if(!window.sceneStyleExporting&&!preview.classList.contains('is-pristine'))renderEdit()});
  let captionDrag=null,captionMoveScope='scene',textDrag=null;
  const moveScope=document.createElement('div');moveScope.className='caption-position';
  moveScope.hidden=true;
  moveScope.innerHTML='<button type="button" data-caption-scope="all" style="grid-column:1/-1">이 위치를 다른 장면에도 적용</button><small style="grid-column:1/-1" data-caption-scope-status></small>';
  const captionPlacement=captionField?.querySelector('.caption-position');
  captionPlacement?.after(moveScope);
  captionPlacement.querySelector('[data-caption-placement="free"]').textContent='위치 옮기기';
  captionPlacement.querySelector('[data-caption-placement="title"]').textContent='위치 초기화';
  const maskDetails=document.createElement('details');maskDetails.style.gridColumn='1/-1';maskDetails.innerHTML='<summary style="cursor:pointer">자막박스 크기 · 색상</summary><div class="caption-position"></div>';
  captionPlacement?.querySelectorAll('label').forEach(label=>maskDetails.querySelector('div').append(label));
  captionPlacement?.append(maskDetails);
  // 자막박스 모양 고르기(2026-09-18) — 기본(템플릿) / 없음 / 10종. 고르면 직접 고른 박스색은 풀린다.
  const lookRow=document.createElement('div');lookRow.className='caption-looks';
  lookRow.innerHTML='<span>자막박스 모양</span>'+[['auto','기본'],['none','박스 없음'],...CAPTION_LOOK_NAMES.map((n,i)=>[String(i),n])].map(([v,n])=>`<button type="button" data-caption-look="${v}">${n}</button>`).join('');
  maskDetails.querySelector('div').prepend(lookRow);
  // 09-19 사장님 '버튼이 다 검정이라 뭐가 뭔지 모르겠다' — 버튼에 그 모양을 그대로 입혀 눈으로 고른다.
  lookRow.querySelectorAll('[data-caption-look]').forEach(button=>{
    const v=button.dataset.captionLook;
    if(v==='auto')return;   // '기본'은 템플릿이 정하므로 칠하지 않는다
    const look=v==='none'?CAPTION_NONE:CAPTION_LOOKS[Number(v)]?.('#43E2B4');if(!look)return;
    Object.assign(button.style,{color:look.color,border:'1px solid #294451',borderRadius:'6px'});
    for(const [k,val] of Object.entries(look.box||{}))if(!['left','width'].includes(k))button.style[k]=val;
    if(v==='none'){button.style.background='#1b1b1b';Object.assign(button.style,look.text||{});}
  });
  function syncCaptionLookButtons(){const saved=captionLayouts.get(captionKey())||{};const cur=saved.look==='none'?'none':Number.isInteger(saved.look)?String(saved.look):'auto';lookRow.querySelectorAll('[data-caption-look]').forEach(b=>b.classList.toggle('active',b.dataset.captionLook===cur));}
  lookRow.addEventListener('click',event=>{
    const b=event.target.closest('[data-caption-look]');if(!b)return;
    const settings={...captionSettings(),...(captionLayouts.get(captionKey())||{})};delete settings.bgUser;delete settings.colorUser;
    if(b.dataset.captionLook==='auto')delete settings.look;else settings.look=b.dataset.captionLook==='none'?'none':Number(b.dataset.captionLook);
    captionLayouts.set(captionKey(),settings);markDirty('caption');renderEdit();syncCaptionLookButtons();
  });
  maskDetails.addEventListener('toggle',syncCaptionLookButtons);
  function applyCaptionMoveScope(){
    moveScope.hidden=false;
    if(captionMoveScope!=='all')return;
    const drag=captionDrags.get(captionKey())||{x:0,y:0},settings=captionSettings(),offset=textOffset('caption');
    for(let i=0;i<sceneTotal();i++){
      const key=`${rows[current].id}:${mode}:${i}:caption`;
      captionDrags.set(key,{...drag});
      captionLayouts.set(key,{...(captionLayouts.get(key)||{}),placement:settings.placement,w:settings.w});
      textOffsets.set(`${rows[current].id}:${mode==='continuous'?'frame':sceneKind(i)}:caption:${i}`,offset);
    }
  }
  moveScope.addEventListener('click',event=>{
    const button=event.target.closest('[data-caption-scope]');if(!button)return;
    captionMoveScope='all';
    applyCaptionMoveScope();
    captionMoveScope='scene';
    moveScope.querySelector('[data-caption-scope-status]').textContent='모든 장면에 적용했어요.';
  });
  // 제목·채널명 끌어 옮기기(2026-09-19 사장님). 자막은 아래 기존 코드가 담당한다.
  preview.addEventListener('pointerdown',event=>{
    if(event.button!==0)return;
    const hit=event.target.closest('.precision-text[data-edit-bind]');
    const bind=hit?.dataset.editBind;
    if(!bind||!['channel','hook1','hook2','bodyTitle'].includes(bind))return;
    const rect=preview.getBoundingClientRect(),origin=textDrags.get(scaleKey(bind))||{x:0,y:0};
    textDrag={pointer:event.pointerId,bind,key:scaleKey(bind),startX:event.clientX,startY:event.clientY,rect,origin,box:hit.getBoundingClientRect()};
    preview.setPointerCapture(event.pointerId);event.preventDefault();
  });
  preview.addEventListener('pointermove',event=>{
    if(!textDrag||event.pointerId!==textDrag.pointer)return;
    const d=textDrag;
    // 미리보기 밖으로 나가지 않게 막는다
    const dx=Math.max(Math.min(0,d.rect.left-d.box.left),Math.min(Math.max(0,d.rect.right-d.box.right),event.clientX-d.startX));
    const dy=Math.max(Math.min(0,d.rect.top-d.box.top),Math.min(Math.max(0,d.rect.bottom-d.box.bottom),event.clientY-d.startY));
    textDrags.set(d.key,{x:d.origin.x+dx/d.rect.width*100,y:d.origin.y+dy/d.rect.height*100});
    markDirty(d.bind);renderEdit();
  });
  for(const type of ['pointerup','pointercancel','lostpointercapture'])preview.addEventListener(type,()=>{if(textDrag)rememberLocal({textDrags:Object.fromEntries(textDrags)});textDrag=null;});   /* 옮긴 자리를 바로 기억 */
  preview.addEventListener('pointerdown',event=>{
    if(event.button!==0||!event.target.closest('[data-edit-bind="caption"]'))return;
    const rect=preview.getBoundingClientRect(),text=layer.querySelector('.precision-text[data-edit-bind="caption"]');if(!text)return;
    const settings=captionSettings();if(settings.placement==='title'){captionLayouts.set(captionKey(),{...settings,placement:'free',w:100});updateCaptionButtons();}
    const bounds=(layer.querySelector('.caption-mask')||text).getBoundingClientRect(),origin=captionDrags.get(captionKey())||{x:0,y:0};
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
  for(const type of ['pointerup','pointercancel','lostpointercapture'])preview.addEventListener(type,()=>{if(captionDrag)applyCaptionMoveScope();captionDrag=null;});
  const premiumFaces=['SBAggroB','YgJalnan','JalnanGothic','Jalnan2','GothicA1Black','GmarketSansBold','GasoekOne','Cafe24Ohsquare','KCCGanpan','BinggraeBold','BlackHanSans','Pretendard','BMDOHYEON','BMJUA','BagelFatOne','DongleBold','Kkubulim','NanumMyeongjoEB','RIDIBatang','HakgyoansimBunpil','NanumBrushScript','GaeguBold','Cafe24Danjunghae','SUITBold','NotoSansKRBold'];
  Promise.all(premiumFaces.map(family=>document.fonts?.load?.(`400 32px "${family}"`))).then(()=>{fittedText.clear();renderEdit()});
  document.fonts?.addEventListener?.('loadingdone',()=>{if(!window.sceneStyleExporting){fittedText.clear();renderEdit()}});
  saveButton&&(saveButton.textContent='현재 설정 저장');
  const initialPreset=Math.max(0,Number(query.get('preset'))||0);
  if(query.get('mode')==='continuous'){modeBar.querySelector('[data-template-mode="continuous"]').click();if(initialPreset<rows.length)selectPreset(initialPreset)}else selectPreset(Math.min(initialPreset,rows.length-1));
  if(mode==='story'&&query.get('frame')==='body')showFrame('body');
  if(!qaMode&&!labMode){
    try{
      const saved=JSON.parse(localStorage.getItem('scene_style_preset')||'null');
      if(saved){
        branding=Object.keys(saved.branding||{}).length?saved.branding:rememberedBranding();
        if(saved.presetId==='t11'&&saved.text?.channel==='이븐쇼핑')saved.text.channel='숏템메이커';
        for(const [name,map] of Object.entries({fontScales,textOffsets,textDrags,colors:colorOverrides,fixedLayouts,fixedColors,captionTexts,captionDrags,captionPositions,captionLayouts}))for(const [key,value] of Object.entries(saved[name]||{}))map.set(key,value);
        if(!query.has('preset')&&!query.has('mode')){
          modeBar.querySelector(`[data-template-mode="${saved.mode==='continuous'?'continuous':'story'}"]`).click();
          const index=rows.findIndex(p=>p.id===saved.presetId);if(index>=0)selectPreset(index);
        }
        if(rows[current].id===saved.presetId){
          const savedScene=saved.sceneIndex??(saved.frameKind==='body'?1:0);
          showScene(query.get('frame')==='hook'?0:query.get('frame')==='body'?Math.max(1,savedScene):savedScene);
          for(const [key,text] of Object.entries(saved.text||{}))if(inputs[key]&&key!=='caption'){inputs[key].value=text;markDirty(key);updateCount(inputs[key]);}
        }
        hookMotion=saved.hookMotion||hookMotion;bodyCaptionMotion=saved.bodyCaptionMotion||'';fontSet=saved.fontSet||'';window.dispatchEvent(new Event('scene-style-fontset'));hookBandMotion=saved.hookBandMotion??((saved.hookBandRise||saved.hookMotion==='rise')?'rise':'');hookMotionSpeed=saved.hookMotionSpeed||hookMotionSpeed;hookCaptionMode=saved.hookCaptionMode||hookCaptionMode;fittedText.clear();syncHookMotionUI();renderEdit();   // 09-19: 복원한 폰트 세트·모션을 화면에 바로 반영renderEdit();syncHookMotionUI();
      }
    }catch(error){console.warn('저장 설정 복원 실패',error);}
  }
  window.sceneStyle={
    snapshot:()=>noTemplate?null:({version:1,mode,presetId:rows[current].id,sceneIndex,frameKind:frameKind(),hookMotion,hookBandMotion,bodyCaptionMotion,fontSet,hookMotionSpeed,hookCaptionMode,branding,text:Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value])),fontScales:Object.fromEntries(fontScales),textOffsets:Object.fromEntries(textOffsets),textDrags:Object.fromEntries(textDrags),colors:Object.fromEntries(colorOverrides),fixedLayouts:Object.fromEntries(fixedLayouts),fixedColors:Object.fromEntries(fixedColors),captionTexts:Object.fromEntries(captionTexts),captionDrags:Object.fromEntries(captionDrags),captionPositions:Object.fromEntries(captionPositions),captionLayouts:Object.fromEntries(captionLayouts),effects}),
    load(context,saved){
      sceneContext=context;
      branding=Object.keys(saved?.branding||{}).length?saved.branding:(labMode?{}:rememberedBranding());
      if(saved){
        for(const [name,map] of Object.entries({fontScales,textOffsets,textDrags,colors:colorOverrides,fixedLayouts,fixedColors,captionTexts,captionDrags,captionPositions,captionLayouts})){
          map.clear();for(const [key,value] of Object.entries(saved[name]||{}))map.set(key,value);
        }
        effects=saved.effects||{};
        hookMotion=saved.hookMotion||hookMotion;bodyCaptionMotion=saved.bodyCaptionMotion||'';fontSet=saved.fontSet||'';window.dispatchEvent(new Event('scene-style-fontset'));hookBandMotion=saved.hookBandMotion??((saved.hookBandRise||saved.hookMotion==='rise')?'rise':'');hookMotionSpeed=saved.hookMotionSpeed||hookMotionSpeed;hookCaptionMode=saved.hookCaptionMode||hookCaptionMode;
        mode=saved.mode==='continuous'?'continuous':'story';rows=mode==='continuous'?fixedRows:storyRows;
        modeBar.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x.dataset.templateMode===mode));
        renderGrid();selectPreset(Math.max(0,rows.findIndex(p=>p.id===saved.presetId)));
        for(const [key,value] of Object.entries(saved.text||{}))if(inputs[key]&&key!=='caption')inputs[key].value=value;
      }
      if(context?.text)for(const [key,value] of Object.entries(context.text))if(inputs[key])inputs[key].value=value;
      if(context?.scenes?.length)showScene(Number.isInteger(saved?.sceneIndex)?saved.sceneIndex:0);
      fittedText.clear();renderEdit();
    },
    show(index){showScene(index);return this.geometry()},
    geometry:()=>({media:noTemplate?{top:0,height:100}:mediaBounds(frameFor(rows[current]),rows[current].id),sceneIndex,kind:sceneKind(sceneIndex)}),
    effect(value){if(value!==undefined)effects[String(sceneIndex)]=value;return effects[String(sceneIndex)]||{}},
    copyEffectsToAll(){const value=structuredClone(effects[String(sceneIndex)]||{});for(let i=0;i<sceneTotal();i++)effects[String(i)]=structuredClone(value);},
    branding(value){if(value!==undefined){branding=value;if(!labMode)try{localStorage.setItem('scene_style_branding',JSON.stringify(value));const saved=JSON.parse(localStorage.getItem('scene_style_preset')||'null');if(saved)localStorage.setItem('scene_style_preset',JSON.stringify({...saved,branding:value}));}catch{}}return branding},
    context:()=>sceneContext,
    validation:()=>templateViolations(),
    resetCaptionText(){captionTexts.delete(captionKey());syncCaption();markDirty('caption');renderEdit()},
    refresh(){fittedText.clear();renderEdit()},
    motionAt(time){return runHookMotion({time})},
    captionEnterAt(time){return runCaptionEnter({time})},   // 고정형 자막 등장(장면 시작 기준 ms) — 렌더러가 장면마다 찍는다
    cameraAt,
  };
  if(!labMode)try{effects=JSON.parse(localStorage.getItem('scene_style_preset')||'null')?.effects||{}}catch{}
})();

// 문구/텍스트 탭 단락 접기(2026-09-18 사장님): 안내 상자는 숨기고, 단락마다 제목이 붙은 한 줄 카드로 기본 접는다.
//   훅 모션 효과 / 빠른 조절 / 제목 / 자막. 칸을 옮기기만 하고 새로 만들지 않는다 — 기존 코드는 선택자(data-field-key 등)로
//   칸을 찾아 숨김·보임만 바꾸므로 위치가 바뀌어도 그대로 돈다. 안내 상자(.ai-card)는 연결 스크립트의 기준점이라 지우지 않고 숨긴다.
(()=>{
  const GROUPS=[
    {key:'motion',title:'훅 모션',pick:p=>[...p.querySelectorAll(':scope > .hook-motion:not(.body-motion)')]},
    {key:'bodyMotion',title:'본문 모션',pick:p=>[...p.querySelectorAll(':scope > .body-motion')]},
    {key:'quick',title:'빠른 조절',pick:p=>[...p.querySelectorAll(':scope > .fixed-quick-panel')]},
    {key:'title',title:'제목',pick:p=>['channel','hook1','hook2','bodyTitle'].map(k=>p.querySelector(`:scope > [data-field-key="${k}"]`)).filter(Boolean)},
    {key:'caption',title:'자막',pick:p=>[p.querySelector(':scope > [data-field-key="caption"]'),p.querySelector(':scope > .scene-line-editor')].filter(Boolean)},
  ];
  const style=document.createElement('style');
  style.textContent=`.scene-text-panel > .ai-card{display:none!important}
  .text-group{border:1px solid #294451;border-radius:12px;background:#0b1a22;margin:0 0 8px}
  .text-group > summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;padding:12px 14px;min-height:22px}
  .text-group > summary::-webkit-details-marker{display:none}
  .text-group > summary b{color:#e8f3f0;font-size:13px;font-weight:900;white-space:nowrap}
  .text-group > summary small{margin-left:auto;color:#63edc6;font-size:10px;font-weight:800;max-width:58%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .text-group > summary::after{content:'▾';color:#8fa3ad;font-size:11px;transition:transform .15s}
  .text-group:not([open]) > summary::after{transform:rotate(-90deg)}
  .text-group[open] > summary{border-bottom:1px solid #1d3440}
  .text-group > .text-group-body{padding:10px 12px 12px}
  .text-group > .text-group-body > section{margin:0;border:0;background:none;padding:0}`;
  document.head.append(style);
  function hint(key,body){
    const val=sel=>body.querySelector(sel)?.value?.trim()||'';
    if(key==='motion'){const m=body.querySelector('.hook-motion-grid .active')?.textContent||'',b=body.querySelector('[data-hook-band-motion].active')?.textContent||'';return [m,b&&b!=='없음'?b:''].filter(Boolean).join(' + ');}
    if(key==='bodyMotion'){const t=body.querySelector('[data-body-caption-motion].active')?.textContent||'';return t==='없음'?'':t;}
    if(key==='quick')return body.querySelector('.fixed-size-control output')?.textContent?`상단 ${body.querySelector('.fixed-size-control output').textContent}`:'';
    if(key==='title')return [...body.querySelectorAll('[data-field-key]:not([hidden]) input')].map(i=>i.value.trim()).filter(Boolean)[1]||val('input');
    if(key==='caption')return val('textarea');
    return '';
  }
  function build(){
    const panel=document.querySelector('.layout-a .scene-text-panel');if(!panel)return;
    for(const g of GROUPS){
      let box=panel.querySelector(`:scope > .text-group[data-group="${g.key}"]`);
      const nodes=g.pick(panel);if(!box&&!nodes.length)continue;
      if(!box){box=document.createElement('details');box.className='text-group';box.dataset.group=g.key;
        box.innerHTML=`<summary><b>${g.title}</b><small></small></summary><div class="text-group-body"></div>`;nodes[0].before(box);}
      const body=box.querySelector('.text-group-body');nodes.forEach(n=>body.append(n));
    }
    // 그룹 순서를 고정(나중에 끼어든 요소가 순서를 바꾸지 않게)
    GROUPS.map(g=>panel.querySelector(`:scope > .text-group[data-group="${g.key}"]`)).filter(Boolean).reduce((prev,cur)=>{if(prev)prev.after(cur);return cur;},null);
    refresh();
  }
  function refresh(){
    document.querySelectorAll('.layout-a .scene-text-panel > .text-group').forEach(box=>{
      const body=box.querySelector('.text-group-body');
      // 안의 칸이 전부 숨겨진 단락(예: 훅 화면의 자막)은 카드째 숨긴다
      // 값이 바뀔 때만 쓴다 — 이 함수가 감시 대상 안을 고치므로, 같은 값을 다시 쓰면 감시→갱신이 끝없이 돈다.
      const hide=![...body.children].some(c=>!c.hidden);if(box.hidden!==hide)box.hidden=hide;
      const small=box.querySelector('summary small'),text=hint(box.dataset.group,body);if(small.textContent!==text)small.textContent=text;
    });
  }
  const start=()=>{build();const panel=document.querySelector('.layout-a .scene-text-panel');if(!panel)return;
    new MutationObserver(()=>{if([...panel.children].some(c=>!c.classList.contains('text-group')&&!c.classList.contains('ai-card')&&GROUPS.some(g=>g.pick(panel).includes(c))))build();else refresh();}).observe(panel,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','class']});
    panel.addEventListener('input',refresh);};
  if(document.readyState==='complete')setTimeout(start,0);else addEventListener('load',()=>setTimeout(start,0));
})();

// 효과 탭 단락 접기(2026-09-19 사장님): 문구 탭과 같은 한 줄 카드로 기본 접는다.
//   워터마크 · 광고 / 화면 확대 · 강조 / 가림막 / 스티커 · 도형 · 배지. 초기화·다른 장면 적용 버튼은 카드 밖 맨 아래.
//   칸은 옮기기만 한다 — connect·decorations·labels는 참조(변수)나 하위 선택자로 칸을 찾으므로 위치가 바뀌어도 돈다.
//   카드 모양은 위 문구 탭의 .text-group 스타일을 그대로 쓴다(한 곳에서 정한다).
(()=>{
  // 효과 패널의 기존 details·section 규칙이 카드에 여백을 더해 문구 탭 카드와 줄이 어긋났다(실측 11~12px) → 0으로
  const style=document.createElement('style');
  style.textContent='.scene-effects-panel .text-group{padding:0!important;margin:0 0 8px!important}';
  document.head.append(style);
  function card(details,key,title){
    details.classList.add('text-group');details.dataset.group=key;details.open=false;
    let summary=details.querySelector(':scope > summary');if(!summary){summary=document.createElement('summary');details.prepend(summary);}
    summary.innerHTML=`<b>${title}</b><small></small>`;
    const body=document.createElement('div');body.className='text-group-body';
    [...details.children].filter(c=>c!==summary).forEach(c=>body.append(c));details.append(body);return details;
  }
  function hint(box){
    const key=box.dataset.group;
    if(key==='brand')return [...box.querySelectorAll('[data-brand]')].filter(r=>r.querySelector('[data-brand-field="on"]')?.checked).map(r=>r.dataset.brand==='ad'?'광고':'워터마크').join(' · ');
    if(key==='zoom'){const z=box.querySelector('[data-effect-value="zoom"]')?.textContent||'',m=box.querySelector('[data-effect-mode].active')?.textContent||'';return [z&&z!=='100%'?`확대 ${z}`:'',m&&m!=='없음'?m:''].filter(Boolean).join(' · ');}
    return '';
  }
  function refresh(panel){panel.querySelectorAll(':scope .text-group[data-group]').forEach(box=>{const s=box.querySelector(':scope > summary small');if(!s)return;const t=hint(box);if(s.textContent!==t)s.textContent=t;});}
  function build(){
    const panel=document.querySelector('.scene-effects-panel');if(!panel||panel.dataset.grouped)return;
    const brand=panel.querySelector(':scope > .scene-label-settings');if(brand)card(brand,'brand','워터마크 · 광고');
    const zoomNodes=[panel.querySelector(':scope > p'),panel.querySelector(':scope > label:has([data-effect="zoom"])'),panel.querySelector(':scope > .scene-effect-choices'),panel.querySelector(':scope > [data-highlight-controls]')].filter(Boolean);
    if(zoomNodes.length){const box=document.createElement('details');zoomNodes[0].before(box);zoomNodes.forEach(n=>box.append(n));card(box,'zoom','화면 확대 · 강조');}
    const deco=panel.querySelector(':scope > .scene-decoration-panel');
    if(deco)deco.querySelectorAll(':scope > details').forEach((d,i)=>{const t=d.querySelector(':scope > summary')?.textContent.trim()||'';card(d,i?'decor':'mask',t||(i?'스티커 · 도형 · 배지':'가림막'));});
    panel.querySelectorAll(':scope > .scene-effects-reset').forEach(b=>panel.append(b));
    panel.dataset.grouped='1';refresh(panel);
    ['input','change','click'].forEach(ev=>panel.addEventListener(ev,()=>setTimeout(()=>refresh(panel),0)));
  }
  if(document.readyState==='complete')setTimeout(build,0);else addEventListener('load',()=>setTimeout(build,0));
})();
