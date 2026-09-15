(()=>{
  const job=document.getElementById('job'),clone=document.getElementById('clone');
  const checks=document.getElementById('checks'),editor=document.getElementById('editor');
  const status=document.getElementById('status'),error=document.getElementById('error');
  let packet=null,jobs=[];

  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const selected=()=>jobs.find(row=>row.job_id===job.value);
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
    }catch(cause){editor.contentWindow.postMessage({type:'scene-style-saved',ok:false,error:cause.message},location.origin)}
  });
  loadJobs().catch(cause=>{error.textContent=cause.message;status.textContent='불러오기 실패'});
})();
