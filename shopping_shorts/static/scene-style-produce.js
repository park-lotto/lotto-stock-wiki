(()=>{
  let dialog,frame,jobId,packet,appliedOnServer=false;
  let saveQueue=Promise.resolve();
  const canaryKey='scene-style-canary-enabled';
  const canaryParam=new URLSearchParams(location.search).get('scene_style_canary');
  const canaryRequested=canaryParam==='1';
  if(canaryRequested)localStorage.setItem(canaryKey,'1');
  if(canaryParam==='0')localStorage.removeItem(canaryKey);
  const canaryEnabled=canaryRequested||localStorage.getItem(canaryKey)==='1';
  // 서버 카나리(canary.py)와 짝 — 관리자 + 이 쿠키일 때만 새 대본 동작. 켜고 끄는 자리는 여기 한 곳.
  document.cookie='ss_canary='+(canaryEnabled?'1':'0')+'; path=/; max-age='+(canaryEnabled?31536000:0)+'; SameSite=Lax';
  window.SS_CANARY=canaryEnabled;
  let canaryRequest=0,canaryJobId='';
  const currentMixJob=()=>String(typeof MIX_JOB==='undefined'?'':(MIX_JOB||'')).trim();
  const status=()=>document.getElementById('sceneStyleStatus');
  const draftKey=id=>'scene-style-draft:'+id;
  // 저장본 비교 — 키 순서·undefined에 흔들리지 않게 정렬해 문자열로 견준다
  const stable=v=>JSON.stringify(v,(k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.keys(x).sort().reduce((o,key)=>{if(x[key]!==undefined)o[key]=x[key];return o},{}):x);
  const sameSnapshot=(a,b)=>stable(a||null)===stable(b||null);
  let serverText=null;   // 이번에 열 때 서버가 준 제목 글 — 임시저장 복원 때 '고친 칸' 판정 기준
  // ★인라인 모드(2026-09-23 사장님: "구버전에서 신버전으로 바꾸는 작업, 라이브 방송 뒤 바로 교체되게 기본 세팅 먼저").
  //   관리자 스위치 scene_style_inline_enabled(기본 끔)가 켜지면 6단계 패널 안에 새 편집기를 바로 띄우고 구버전 UI를 숨긴다.
  //   팝업(dialog)과 **같은 iframe·같은 메시지 흐름**을 쓴다 — 갈라 두면 둘이 어긋난다(0순위-B). 끄면 종전 화면 그대로.
  let inlineMode=false,inlineShell=null,inlineOpen=false;
  const editorOpen=()=>inlineMode?inlineOpen:!!dialog?.open;
  const stepPanel=()=>document.querySelector('.panel[data-step="3"]');
  function ensureInlineShell(){
    const panel=stepPanel();if(!panel||inlineShell)return inlineShell;
    if(!document.getElementById('sceneStyleInlineStyle')){const style=document.createElement('style');style.id='sceneStyleInlineStyle';
      // ★되살리는 선택자는 **id**로 받는다 — 위 숨김 규칙의 `:not(#sceneStyleInline)`이 ID 점수를 가져가
      //   클래스·속성만으로는 항상 진다(2026-09-24 실측: 규칙 둘 다 걸렸는데 숨김이 이겼다).
      // ★원본 모드(plain)에서는 옛 헤드카피·자막 칸을 다시 보여 준다 — 그 모드는 새 편집기가 글자를 안 그리고
      //   렌더가 옛 경로를 타서, 이 칸들이 실제로 결과물에 반영되는 자리다(2026-09-24).
      style.textContent='.panel[data-step="3"].scene-style-inline-active>:not(h3):not(#sceneStyleInline){display:none!important}'
                // ★옛 화면은 더 이상 꺼내지 않는다(2026-09-24 사장님: "구버전으로 이동하게 한 거야?").
        //   헤드카피·자막은 새 편집기 오른쪽 '문구/텍스트' 안에 같은 카드 모양으로 들어갔다.
        //   이 규칙은 값을 읽고 쓰기 위해 옛 칸을 **화면 밖에** 살려 두는 용도다(display:none이면 값이 안 읽힌다).
        +'.panel[data-step="3"].scene-style-inline-active.scene-style-plain>#legacyDecoWrap{position:absolute!important;left:-9999px!important;width:1px!important;height:1px!important;overflow:hidden!important}';document.head.append(style);}
    inlineShell=document.createElement('section');inlineShell.id='sceneStyleInline';inlineShell.style.cssText='margin-top:10px';
    const note=document.createElement('div');note.id='sceneStyleInlineStatus';note.setAttribute('role','status');note.style.cssText='margin:0 0 8px;color:#bdeee5;font-size:13px';
    frame=document.createElement('iframe');frame.title='문구와 효과 편집기';frame.style.cssText='width:100%;height:calc(100vh - 200px);min-height:720px;border:1px solid #35505b;border-radius:12px;background:#071118';
    inlineShell.append(note,frame);panel.append(inlineShell);return inlineShell;
  }
  let allowed=false;   // 새 편집기를 열 수 있는가 — 관리자 또는 스위치(2026-09-23 사장님: 라이브 뒤 켠다. 그전엔 고객에게 안 보인다)
  async function initInline(){
    try{const r=await fetch('/api/produce/scene-style/flags',{cache:'no-store'});const d=await r.json();inlineMode=!!(r.ok&&d&&d.inline);allowed=!!(r.ok&&d&&d.allowed);}catch(_){inlineMode=false;allowed=false;}
    if(!allowed){const btn=document.querySelector('.panel[data-step="3"] button.btn[onclick="openSceneStyleEditor()"]');if(btn)btn.hidden=true;const st=status();if(st)st.textContent='';}
    if(!inlineMode)return;
    const panel=stepPanel();if(!panel)return;
    ensureInlineShell();
    // 6단계 패널이 보이면 자동으로 열고, 떠나면 임시저장(+적용한 job은 서버 저장) — 사용자가 누를 버튼이 없다
    const sync=()=>{const visible=panel.classList.contains('show');
      if(visible&&MIX_JOB&&(!inlineOpen||jobId!==MIX_JOB))openSceneStyleEditor();
      else if(!visible&&inlineOpen)leaveInline();};
    new MutationObserver(sync).observe(panel,{attributes:true,attributeFilter:['class']});sync();
  }
  async function leaveInline(){
    try{const api=frame?.contentWindow?.sceneStyle;if(api?.context()?.jobId===jobId&&applied())await saveSnapshot(stashDraft());else stashDraft();}catch(error){status().textContent=error.message;}
    inlineOpen=false;
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initInline);else initInline();
  const timelineKey=context=>JSON.stringify(context.scenes.map(s=>[s.beat_idx,s.start,s.end,s.caption]));
  function showCanaryFallback(message){
    const panel=document.querySelector('.panel[data-step="3"]');
    const shell=document.getElementById('sceneStyleCanary');
    const note=document.getElementById('sceneStyleCanaryStatus');
    const lab=document.getElementById('sceneStyleCanaryFrame');
    panel?.classList.remove('scene-style-canary-active');
    if(shell)shell.hidden=!canaryEnabled;
    if(note)note.textContent=message||'';
    if(lab)lab.style.display='none';
  }
  window.syncSceneStyleCanary=async()=>{
    if(!canaryEnabled)return false;
    const panel=document.querySelector('.panel[data-step="3"]');
    const shell=document.getElementById('sceneStyleCanary');
    const note=document.getElementById('sceneStyleCanaryStatus');
    const lab=document.getElementById('sceneStyleCanaryFrame');
    if(!panel||!shell||!note||!lab)return false;
    const requested=currentMixJob();
    if(!requested){showCanaryFallback('현재 작업 번호가 아직 없습니다. 기존 장면꾸미기를 유지합니다.');return false;}
    if(canaryJobId===requested&&panel.classList.contains('scene-style-canary-active'))return true;
    const request=++canaryRequest;
    showCanaryFallback('관리자 권한과 현재 작업을 확인하는 중…');
    try{
      const response=await fetch('/api/admin/scene-style-lab/jobs',{cache:'no-store'});
      const data=await response.json();
      if(!response.ok)throw Error(data.error||'관리자 LAB 권한을 확인하지 못했습니다.');
      if(request!==canaryRequest||requested!==currentMixJob())return false;
      const exact=(data.jobs||[]).find(row=>String(row.job_id)===requested);
      if(!exact)throw Error('현재 작업이 관리자 LAB 목록에 없습니다. 다른 작업으로 대신 열지 않습니다.');
      canaryJobId=requested;
      shell.hidden=false;note.textContent=`관리자 시험 모드 · 현재 작업 ${requested}의 복사본만 사용합니다.`;
      const target='/scene_style_lab.html?embedded=tab&job='+encodeURIComponent(requested);
      if(lab.dataset.jobId!==requested){lab.dataset.jobId=requested;lab.src=target;}
      lab.style.display='block';panel.classList.add('scene-style-canary-active');
      return true;
    }catch(error){
      if(request===canaryRequest)showCanaryFallback(`${error.message} 기존 장면꾸미기를 유지합니다.`);
      return false;
    }
  };
  if(canaryEnabled){
    const style=document.createElement('style');
    style.textContent='.panel[data-step="3"].scene-style-canary-active>:not(h3):not(#sceneStyleCanary){display:none!important}';
    document.head.append(style);
    setTimeout(()=>window.syncSceneStyleCanary(),0);
  }
  function stashDraft(){
    const api=frame?.contentWindow?.sceneStyle;
    if(!editorOpen()||api?.context()?.jobId!==jobId)return null;
    const snapshot=api.snapshot();
    // baseText = 이 편집기를 열 때 서버가 준 제목 글(임시저장 병합 전). 복원할 때 여기서 달라진 칸만 '사용자가 고친 것'으로 본다.
    try{localStorage.setItem(draftKey(jobId),JSON.stringify({snapshot,timeline:timelineKey(packet.context),baseText:serverText||{}}));}catch(error){status().textContent='임시 저장 공간이 부족합니다. 저장하고 닫기를 눌러 주세요.';}
    return snapshot;
  }
  // ★자동 저장은 **이미 [이 영상에 적용]을 누른 적 있는 job에서만** 한다(2026-09-16 사장님 제보).
  //   스냅샷에는 '템플릿 없음'이라는 상태가 없다(scene_style.validate_snapshot이 presetId 필수) —
  //   그래서 열었다 그냥 닫기만 해도 기본 t11이 저장됐고, 렌더(video_assemble)가 그걸 그대로
  //   합성해 "템플릿 안 썼는데 들어가 있다"가 됐다(실측 job 53c0d41edc39: template=null인데
  //   scene_style=t11, 편집 흔적 0). 임시저장(localStorage)은 그대로 둔다 — 그건 서버에 안 간다.
  //   ★판정은 packet.snapshot이 아니라 이 깃발로 한다 — 임시저장 복원이 packet.snapshot을
  //   덮어써서, 두 번째로 열었다 닫을 때 "적용한 적 있다"로 잘못 읽히는 구멍이 있다.
  const applied=()=>appliedOnServer;
  addEventListener('pagehide',()=>{
    const snapshot=stashDraft();if(!snapshot||!applied())return;
    fetch('/api/produce/mix/settings',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jobId,scene_style:snapshot})}).catch(()=>{});
  });
  function saveSnapshot(snapshot){
    const id=jobId,copy=structuredClone(snapshot);
    const task=saveQueue.catch(()=>{}).then(async()=>{
      if(id!==MIX_JOB||id!==jobId)throw Error('편집 중인 영상이 바뀌었습니다. 다시 열어 주세요.');
      const response=await fetch('/api/produce/mix/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:id,scene_style:copy})});
      const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'영상 설정을 저장하지 못했습니다.');
      if(id===MIX_JOB&&id===jobId){STATE.deco={...(STATE.deco||{}),scene_style:copy};packet.snapshot=copy;appliedOnServer=true;saveWork();status().textContent=copy?'문구·효과 적용됨 · 최종 영상에 반영됩니다.':'템플릿 없음 · 원본 영상 그대로 나갑니다.';}
      try{const draft=JSON.parse(localStorage.getItem(draftKey(id))||'null');if(draft&&JSON.stringify(draft.snapshot)===JSON.stringify(copy))localStorage.removeItem(draftKey(id));}catch(_){}
    });
    saveQueue=task;return task;
  }
  async function saveAndClose(){
    try{
      const api=frame?.contentWindow?.sceneStyle;
      // 닫기·ESC는 **적용한 적 있는 job만** 저장한다(위 applied() 주석과 같은 이유).
      if(api?.context()?.jobId===jobId&&applied())await saveSnapshot(stashDraft());
      else stashDraft();
      if(dialog?.open)dialog.close();
    }catch(error){status().textContent=error.message;frame.contentWindow.postMessage({type:'scene-style-saved',ok:false,error:error.message},location.origin);}
  }
  function remapSnapshot(snapshot,previous,next,changedBeat){
    const result=structuredClone(snapshot),sources=next.scenes.map(scene=>{
      const choices=previous.scenes.map((s,i)=>({s,i})).filter(x=>x.s.beat_idx===scene.beat_idx);
      return (choices.find(x=>x.s.caption===scene.caption&&x.s.start===scene.start)||choices.find(x=>x.s.start<=scene.start&&x.s.end>scene.start)||choices[0])?.i;
    });
    for(const name of ['captionTexts','captionLayouts','captionDrags','captionPositions','fontScales','textOffsets']){
      const output={};for(const [key,value] of Object.entries(snapshot[name]||{})){
        const m=key.match(/^(.*:(?:story|continuous):)(\d+)(:caption)$/)||key.match(/^(.*:caption:)(\d+)()$/);
        if(!m){output[key]=value;continue;}
        sources.forEach((source,i)=>{if(source===Number(m[2])&&!(name==='captionTexts'&&next.scenes[i].beat_idx===changedBeat))output[m[1]+i+m[3]]=value});
      }result[name]=output;
    }
    result.effects={};sources.forEach((source,i)=>{if(snapshot.effects?.[source])result.effects[i]=snapshot.effects[source]});return result;
  }
  window.openSceneStyleEditor=async()=>{
    if(!allowed){status().textContent='';return;}   // 고객에겐 아직 안 연다(관리자·스위치만)
    if(!MIX_JOB){status().textContent='영상의 음성·장면을 먼저 준비해 주세요.';return;}
    jobId=MIX_JOB;status().textContent='실제 제목과 자막을 불러오는 중…';
    try{
      // ★제목·소제목은 **누르지 않아도 들어가 있어야 한다**(2026-09-22 사장님:
      //   "그냥 자동화가 되는 과정이야 눌러야 되는 거 없이 처음에 배치까지 잘 되야 하는 거야").
      //   진입할 때 loadHeadcopySuggest가 후보를 자동으로 뽑아 window._hcCopies에 담아 둔다.
      //   여기서 그 1번을 대비책으로 쓴다 — 옛 꾸미기(produce.html frPick)가 이미 쓰는
      //   `hcText.value || _hcFirstCopy()`와 **같은 규칙**이다(0순위-B: 같은 판단을 두 벌로 두지 않는다).
      //   안 쓰면 서버가 첫 나레이션을 제목에 넣어 "아니 텀블러이 / 있다고?"가 나온다(실측).
      // ★후보가 아직 안 왔으면 기다린다(2026-09-22 라이브 저널: 컨텍스트 17:15:28 제목 빈칸 → 후보 17:15:32 도착.
      //   회색 버튼을 후보보다 먼저 누르면 서버가 대본 첫 문장을 제목에 넣어 12/10자·23/22자로 넘쳤다).
      //   loadHeadcopySuggest는 진행 중이면 같은 약속을 돌려주므로 중복 호출이 아니다.
      if(!(STATE.headcopy?.text)&&!((typeof _hcFirstCopy==='function'&&_hcFirstCopy()))&&typeof loadHeadcopySuggest==='function'){
        status().textContent='대본으로 제목 후보를 뽑는 중…';
        try{await loadHeadcopySuggest(false);}catch(e){}
      }
      const fallbackCopy=(typeof _hcFirstCopy==='function'&&_hcFirstCopy())||'';
      const fallbackSubline=(typeof _hcPickedSubline==='function'&&_hcPickedSubline())
                          ||(typeof _hcFirstSubline==='function'&&_hcFirstSubline())||'';
      // ★2026-09-23 사장님 "대본에 있는 제목 훅이 안 들어온다": 사장님이 직접 정한 제목만
      //   headcopy_text로 보내고, AI 후보는 ai_copy(대비책)로 보낸다. 서버가 **대본 첫 줄**을
      //   먼저 쓰고, 그 줄이 두 줄에 안 담길 때만 AI 후보로 물러난다(hook_from_script 한 곳).
      //   전엔 여기서 AI 후보를 제목 자리에 바로 넣어 대본 제목이 영영 안 들어왔다.
      const params=new URLSearchParams({
        headcopy_text:STATE.headcopy?.text||'',
        ai_copy:fallbackCopy||'',
        headcopy_subline:STATE.headcopy?.subline||fallbackSubline
                        ||document.getElementById('frTitle')?.value||'',
        copy_family:STATE.headcopy?.copy_family||STATE.script_copy_family||''
      });
      const response=await fetch('/api/produce/scene-style/context/'+encodeURIComponent(jobId)+'?'+params);
      packet=await response.json();if(!response.ok)throw Error(packet.error||'장면을 불러오지 못했습니다.');
      serverText={...(packet.context?.text||{})};
      appliedOnServer=!!packet.snapshot;   // 서버에 이미 저장된 설정이 있는 job만 자동 저장 대상
      try{
        const draft=JSON.parse(localStorage.getItem(draftKey(jobId))||'null');
        if(draft?.timeline===timelineKey(packet.context)){
          // ★적용한 적 없는 job이면 임시저장본은 **편집기에만** 돌려놓고 서버엔 안 올린다.
          //   여기서 올리면 열었다 닫기만 한 사람도 결국 템플릿이 박힌다(applied() 주석 참조).
          // ★제목 글은 **사용자가 고친 칸만** 되살린다(2026-09-22 사장님: 같은 작업을 다시 열어도 첫 문장 제목이 그대로).
          //   임시저장본 text는 모든 칸의 값이라, 그대로 덮으면 서버가 새로 준 제목(후보 1번)이 옛 값에 밀린다.
          //   열 때의 서버 글(baseText)과 다른 칸만 사용자 편집으로 본다. baseText가 없는 옛 임시저장본은 글을 되살리지 않는다.
          if(draft.snapshot){
            const base=draft.baseText,all=draft.snapshot.text||{};
            const edited=base?Object.fromEntries(Object.entries(all).filter(([k,v])=>base[k]!==v)):{};
            // ★서버에 올릴 땐 **완전한 글**(서버 저장본 글 + 고친 칸)로 만든다 — 고친 칸만 담긴 조각을 올리면 서버가
            //   "설정이 바뀌었다"고 보고 완성본을 무효화한다(2026-09-22 21:05 실측: 열기만 했는데 렌더가 사라짐, 3단계 재다운로드).
            draft.snapshot.text={...((packet.snapshot&&packet.snapshot.text)||serverText||{}),...edited};
          }
          const serverSnap=packet.snapshot;
          packet.snapshot=draft.snapshot;if(draft.snapshot)packet.context.text={...packet.context.text,...draft.snapshot.text};
          // ★서버 저장본과 실제로 다를 때만 올린다 — 같은데 올리면 저장 시각만 바뀌고 완성본이 무효화된다.
          if(applied()&&!sameSnapshot(draft.snapshot,serverSnap))await saveSnapshot(draft.snapshot);
        }
      }catch(error){status().textContent='남겨둔 편집을 복원했습니다. 서버 저장은 다시 시도해 주세요.';}
      if(inlineMode){
        ensureInlineShell();const panel=stepPanel();panel.classList.add('scene-style-inline-active');
        const note=document.getElementById('sceneStyleInlineStatus');if(note)note.textContent='';
        frame.src='/api/produce/scene-style/assets/out/scene-style-ui-showcase.html?embedded=1';inlineOpen=true;status().textContent='';return;
      }
      if(!dialog){
        dialog=document.createElement('dialog');Object.assign(dialog.style,{width:'98vw',maxWidth:'none',height:'96vh',maxHeight:'none',padding:'0',border:'1px solid #35505b',background:'#08151d',color:'white'});
        const bar=document.createElement('div');bar.style.cssText='display:flex;justify-content:space-between;align-items:center;padding:8px 18px';
        const title=document.createElement('b');title.textContent='장면꾸미기';
        const close=document.createElement('button');close.textContent='저장하고 닫기';close.onclick=saveAndClose;bar.append(title,close);
        dialog.addEventListener('cancel',event=>{event.preventDefault();saveAndClose();});
        frame=document.createElement('iframe');frame.title='문구와 효과 편집기';frame.style.cssText='width:100%;height:calc(100% - 45px);border:0';dialog.append(bar,frame);document.body.append(dialog);
      }
      frame.src='/api/produce/scene-style/assets/out/scene-style-ui-showcase.html?embedded=1';dialog.showModal();status().textContent='';
    }catch(error){status().textContent=error.message;}
  };
  addEventListener('message',async event=>{
    if(event.data?.type==='scene-style-legacy'){
      // 새 편집기 카드에서 바꾼 값을 옛 칸에 그대로 넣고, 옛 저장 흐름(hcTouched/capTouched)을 깨운다.
      const el=document.getElementById(event.data.id);if(!el)return;
      if(el.type==='checkbox')el.checked=!!event.data.value;else el.value=event.data.value;
      el.dispatchEvent(new Event(el.type==='checkbox'||el.tagName==='SELECT'?'change':'input',{bubbles:true}));
      return;
    }
    if(event.data?.type==='scene-style-template'){
      const panel=stepPanel();if(panel)panel.classList.toggle('scene-style-plain',!!event.data.plain);
      // 헤드카피 칸은 옛 '문구' 탭 안에 있다 — 원본 모드로 들어오면 그 탭을 열어 준다(안 열면 빈 화면으로 보인다).
      if(event.data.plain){
        // 편집기 카드에 지금 값을 채워 준다(빈칸으로 열리지 않게).
        const ids=['hcText','hcSize','hcY','hcColor','capColor','capOutline','capBox'];
        const values={};
        for(const id of ids){const el=document.getElementById(id);if(!el)continue;values[id]=el.type==='checkbox'?el.checked:el.value;}
        frame.contentWindow?.postMessage({type:'scene-style-legacy-values',values},location.origin);
      }
      return;
    }
    if(!frame||event.source!==frame.contentWindow||event.origin!==location.origin)return;
    if(event.data?.type==='scene-style-ready')frame.contentWindow.postMessage({type:'scene-style-context',...packet},location.origin);
    // 09-22 편집기의 [이 장면을 썸네일 후보로]: 7단계를 이미 열어 봤으면 후보 목록을 바로 다시 그리고, [썸네일 단계로 이동]은 저장하고 닫은 뒤 7단계로 보낸다.
    if(event.data?.type==='scene-style-thumb-pinned'){if(typeof THUMB_STATE!=='undefined'&&THUMB_STATE.job===MIX_JOB&&typeof loadThumbFrames==='function')loadThumbFrames();return;}
    if(event.data?.type==='scene-style-goto-thumb'){await saveAndClose();if(!dialog?.open&&typeof stepGo==='function')stepGo('thumb');return;}
    if(event.data?.type==='scene-style-lines'){
      try{
        if(event.data.jobId!==jobId||jobId!==MIX_JOB)throw Error('편집 중인 영상이 바뀌었습니다. 다시 열어 주세요.');
        const response=await fetch('/api/produce/mix/'+encodeURIComponent(jobId)+'/caplines',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({beat_idx:event.data.beatIdx,lines:event.data.lines,reset:event.data.reset})});
        const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'줄 저장 실패');
        const refreshed=await fetch('/api/produce/scene-style/context/'+encodeURIComponent(jobId));const next=await refreshed.json();if(!refreshed.ok)throw Error(next.error||'새 자막을 불러오지 못했습니다.');
        const snapshot=event.data.snapshot?remapSnapshot(event.data.snapshot,packet.context,next.context,event.data.beatIdx):null,deco={...(STATE.deco||{}),scene_style:snapshot};   // null = 템플릿 없음
        if(snapshot)next.context.text={...next.context.text,...snapshot.text};
        const saved=await fetch('/api/produce/mix/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jobId,deco})});const answer=await saved.json();if(!saved.ok||!answer.ok)throw Error(answer.error||'줄은 저장했지만 꾸미기 설정 저장에 실패했습니다.');
        STATE.deco=deco;saveWork();packet={...next,snapshot};const index=Math.max(0,next.context.scenes.findIndex(s=>s.beat_idx===event.data.beatIdx));
        frame.contentWindow.postMessage({type:'scene-style-context',...packet,sceneIndex:index},location.origin);
        frame.contentWindow.postMessage({type:'scene-style-lines-result',ok:true},location.origin);
      }catch(error){frame.contentWindow.postMessage({type:'scene-style-lines-result',ok:false,error:error.message},location.origin);}
      return;
    }
    if(event.data?.type!=='scene-style-save')return;
    if(event.data.jobId!==jobId||jobId!==MIX_JOB){frame.contentWindow.postMessage({type:'scene-style-saved',ok:false,error:'편집 중인 영상이 바뀌었습니다. 다시 열어 주세요.'},location.origin);return;}
    try{
      await saveSnapshot(event.data.snapshot);
      frame.contentWindow.postMessage({type:'scene-style-saved',ok:true},location.origin);
    }catch(error){frame.contentWindow.postMessage({type:'scene-style-saved',ok:false,error:error.message},location.origin);}
  });
})();
