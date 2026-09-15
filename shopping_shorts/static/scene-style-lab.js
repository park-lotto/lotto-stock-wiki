(()=>{
  const job=document.getElementById('job'),clone=document.getElementById('clone');
  const checks=document.getElementById('checks'),editor=document.getElementById('editor');
  const status=document.getElementById('status'),error=document.getElementById('error');
  const outputs=document.getElementById('outputs'),render=document.getElementById('render');
  const capcut=document.getElementById('capcut'),landing=document.getElementById('landing');
  const compare=document.getElementById('compare'),resultVideo=document.getElementById('resultVideo');
  let packet=null,jobs=[];
  const initialLab=new URLSearchParams(location.search).get('lab');

  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const selected=()=>jobs.find(row=>row.job_id===job.value);
  const labUrl=suffix=>`/api/admin/scene-style-lab/${encodeURIComponent(packet.manifest.lab_id)}${suffix}`;
  function contractFromContext(){
    const scenes=packet.context.scenes||[],visible=scenes.filter(s=>s.caption&&s.caption_visible!==false);
    const body=visible.find(s=>s.kind==='body');
    return {hook_caption_count:visible.filter(s=>s.kind==='hook').length,body_first_start:body?Number(body.start):null,clean_signature:packet.manifest.clean?.signature||''};
  }
  function cell(ok,text){return `<td class="${ok===null?'pending':ok?'pass':'fail'}">${ok===null?'대기':ok?'PASS':'FAIL'}<br><small>${esc(text||'')}</small></td>`}
  function renderCompare(){
    if(!packet)return;
    const expected=contractFromContext(),contracts=packet.manifest.contracts||{};
    const cols=[['미리보기',expected],['MP4',contracts.mp4],['CapCut',contracts.capcut],['랜딩',contracts.landing]];
    const value=(name,actual,key)=>{if(!actual)return [null,'아직 생성 안 됨'];if((name==='MP4'||name==='랜딩')&&(key==='hook'||key==='body'))return [null,'실물 육안 확인'];if(key==='hook')return [actual.hook_caption_count===0,`${actual.hook_caption_count}개`];if(key==='body'){const ok=expected.body_first_start===null?actual.body_first_start===null:Math.abs(Number(actual.body_first_start)-expected.body_first_start)<=.034;return [ok,actual.body_first_start===null?'-':Number(actual.body_first_start).toFixed(3)+'초']}return [actual.clean_signature===expected.clean_signature,String(actual.clean_signature||'-').slice(0,12)]};
    const rows=[['훅 자막','hook'],['본문 첫 시작','body'],['청소본','clean']];
    compare.innerHTML=rows.map(([label,key])=>`<tr><th>${label}</th>${cols.map(([name,actual])=>cell(...value(name,actual,key))).join('')}</tr>`).join('')+
      `<tr><th>위치</th>${cell(true,'화면 컨텍스트')}${cell(!!packet.manifest.receipts?.mp4,packet.manifest.receipts?.mp4?'실파일 해시':'-')}${cell(!!packet.manifest.outputs?.capcut_project,packet.manifest.outputs?.capcut_project?'JSON 역검증':'-')}${cell(!!packet.manifest.contracts?.landing?.artifact_sha256,packet.manifest.contracts?.landing?.artifact_sha256?'동일 MP4 해시':'-')}</tr>`;
    const ready=!!packet.manifest.outputs?.mp4;resultVideo.hidden=!ready;if(ready)resultVideo.src=labUrl('/video')+'?v='+Date.now();
    landing.href=`/scene-style-lab/${encodeURIComponent(packet.manifest.lab_id)}`;
  }
  async function reloadPacket(){const response=await fetch(labUrl(''),{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'시험 자료를 읽지 못했습니다');packet=data;outputs.hidden=false;renderCompare();return data}
  function renderChecks(row){
    if(!row){checks.innerHTML='';return}
    checks.innerHTML=`<div class="check"><b>음성</b>${row.tts_ready?'준비됨':'부족'}</div><div class="check"><b>청소본</b>${row.clean_ready?'현재 편성 일치':'없음/낡음'}</div><div class="check"><b>장면</b>${row.beat_count}개 비트</div><div class="check"><b>편성 서명</b>${esc(row.clean_signature||'-')}</div>`;
    clone.disabled=!(row.tts_ready&&row.clean_ready);
  }
  async function loadJobs(){
    const response=await fetch('/api/admin/scene-style-lab/jobs',{cache:'no-store'});
    const data=await response.json();if(!response.ok)throw Error(data.error||'작업을 읽지 못했습니다');
    jobs=data.jobs||[];job.innerHTML=jobs.map(row=>`<option value="${esc(row.job_id)}">${esc(row.title)} · ${esc(row.job_id)}</option>`).join('');
    renderChecks(selected());status.textContent=jobs.length?'시험할 작업을 고르세요':'시험 가능한 작업이 없습니다';
  }
  job.addEventListener('change',()=>renderChecks(selected()));
  clone.addEventListener('click',async()=>{
    error.textContent='';clone.disabled=true;status.textContent='시험 복사본 만드는 중…';
    try{
      const response=await fetch('/api/admin/scene-style-lab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job.value})});
      const created=await response.json();if(!response.ok)throw Error(created.error||'시험 복사본을 만들지 못했습니다');
      const loaded=await fetch('/api/admin/scene-style-lab/'+encodeURIComponent(created.manifest.lab_id),{cache:'no-store'});
      packet=await loaded.json();if(!loaded.ok)throw Error(packet.error||'시험 자료를 읽지 못했습니다');
      editor.hidden=false;editor.src='/api/produce/scene-style/assets/out/scene-style-ui-showcase.html?embedded=1&lab=1';
      outputs.hidden=false;renderCompare();
      status.textContent='LAB 복사본 · 훅 말자막 숨김';
    }catch(cause){error.textContent=cause.message;status.textContent='시험 시작 실패';renderChecks(selected())}
  });
  addEventListener('message',async event=>{
    if(event.origin!==location.origin||event.source!==editor.contentWindow||!packet)return;
    if(event.data?.type==='scene-style-ready'){
      editor.contentWindow.postMessage({type:'scene-style-context',context:packet.context,snapshot:packet.snapshot},location.origin);return;
    }
    if(event.data?.type==='scene-style-lines'){
      editor.contentWindow.postMessage({type:'scene-style-lines-result',ok:false,error:'LAB에서는 원본 자막 나누기를 바꾸지 않습니다.'},location.origin);return;
    }
    if(event.data?.type!=='scene-style-save')return;
    try{
      const response=await fetch(`/api/admin/scene-style-lab/${encodeURIComponent(packet.manifest.lab_id)}/snapshot`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({snapshot:event.data.snapshot})});
      const data=await response.json();if(!response.ok)throw Error(data.error||'저장 실패');packet.snapshot=data.snapshot;
      editor.contentWindow.postMessage({type:'scene-style-saved',ok:true},location.origin);status.textContent='LAB에 저장됨 · 원본 무변경';
      await reloadPacket();
    }catch(cause){editor.contentWindow.postMessage({type:'scene-style-saved',ok:false,error:cause.message},location.origin)}
  });
  render.addEventListener('click',async()=>{
    error.textContent='';render.disabled=true;status.textContent='시험 MP4 만드는 중…';
    try{const response=await fetch(labUrl('/render'),{method:'POST'}),data=await response.json();if(!response.ok)throw Error(data.error||'렌더 시작 실패');
      for(let i=0;i<120;i++){await new Promise(resolve=>setTimeout(resolve,1000));await reloadPacket();const state=packet.manifest.render_state||{};if(state.status==='error')throw Error(state.error||'렌더 실패');if(state.status==='ready'&&packet.manifest.outputs?.mp4)break}
      if(packet.manifest.render_state?.status!=='ready'||!packet.manifest.outputs?.mp4)throw Error('렌더가 제한 시간 안에 끝나지 않았습니다');status.textContent='시험 MP4 완료 · 실파일 검증됨';
    }catch(cause){error.textContent=cause.message;status.textContent='시험 MP4 실패'}finally{render.disabled=false}
  });
  async function detectCapCutRoot(dir){
    const tally=new Map();let looked=0;
    for await(const [,handle] of dir.entries()){if(handle.kind!=='directory'||looked++>=12)continue;try{const file=await handle.getFileHandle('draft_meta_info.json');const root=JSON.parse(await(await file.getFile()).text()).draft_root_path;if(root)tally.set(root,(tally.get(root)||0)+1)}catch(_){}}
    return [...tally.entries()].sort((a,b)=>b[1]-a[1])[0]?.[0]||'C:\\capcutproject\\CapCut Drafts';
  }
  async function writeFile(dir,name,value){const handle=await dir.getFileHandle(name,{create:true}),writer=await handle.createWritable();await writer.write(value);await writer.close()}
  capcut.addEventListener('click',async()=>{
    error.textContent='';if(!('showDirectoryPicker' in window)){error.textContent='Chrome 또는 Edge에서 열어 주세요';return}
    capcut.disabled=true;status.textContent='CapCut 시험 초안 만드는 중…';
    try{const root=await window.showDirectoryPicker({mode:'readwrite'}),base=await detectCapCutRoot(root);const response=await fetch(labUrl('/capcut')+'?base='+encodeURIComponent(base),{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'CapCut 생성 실패');const project=await root.getDirectoryHandle(data.project,{create:true});for(const [name,text] of Object.entries(data.texts||{}))await writeFile(project,name,text);for(const asset of data.assets||[]){const got=await fetch(asset.url);if(!got.ok)throw Error('CapCut 재료 다운로드 실패: '+asset.name);await writeFile(project,asset.name,await got.arrayBuffer())}await reloadPacket();status.textContent='CapCut 시험 초안 전송 완료';
    }catch(cause){if(cause?.name!=='AbortError'){error.textContent=cause.message;status.textContent='CapCut 시험 실패'}}finally{capcut.disabled=false}
  });
  loadJobs().then(async()=>{
    if(!initialLab)return;
    const response=await fetch('/api/admin/scene-style-lab/'+encodeURIComponent(initialLab),{cache:'no-store'});
    const data=await response.json();if(!response.ok)throw Error(data.error||'기존 시험을 읽지 못했습니다');
    packet=data;editor.hidden=false;editor.src='/api/produce/scene-style/assets/out/scene-style-ui-showcase.html?embedded=1&lab=1';outputs.hidden=false;renderCompare();status.textContent='기존 LAB 시험 열림';
  }).catch(cause=>{error.textContent=cause.message;status.textContent='불러오기 실패'});
})();
