(()=>{
  let dialog,frame,jobId,packet;
  const status=()=>document.getElementById('sceneStyleStatus');
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
    if(!MIX_JOB){status().textContent='영상의 음성·장면을 먼저 준비해 주세요.';return;}
    jobId=MIX_JOB;status().textContent='실제 제목과 자막을 불러오는 중…';
    try{
      const response=await fetch('/api/produce/scene-style/context/'+encodeURIComponent(jobId)+'?headcopy_text='+encodeURIComponent(STATE.headcopy?.text||''));
      packet=await response.json();if(!response.ok)throw Error(packet.error||'장면을 불러오지 못했습니다.');
      if(!dialog){
        dialog=document.createElement('dialog');Object.assign(dialog.style,{width:'98vw',maxWidth:'none',height:'96vh',maxHeight:'none',padding:'0',border:'1px solid #35505b',background:'#08151d',color:'white'});
        const bar=document.createElement('div');bar.style.cssText='display:flex;justify-content:space-between;align-items:center;padding:8px 18px';
        const title=document.createElement('b');title.textContent='장면꾸미기';
        const close=document.createElement('button');close.textContent='닫기';close.onclick=()=>dialog.close();bar.append(title,close);
        frame=document.createElement('iframe');frame.title='문구와 효과 편집기';frame.style.cssText='width:100%;height:calc(100% - 45px);border:0';dialog.append(bar,frame);document.body.append(dialog);
      }
      frame.src='/api/produce/scene-style/assets/out/scene-style-ui-showcase.html?embedded=1';dialog.showModal();status().textContent='';
    }catch(error){status().textContent=error.message;}
  };
  addEventListener('message',async event=>{
    if(!frame||event.source!==frame.contentWindow||event.origin!==location.origin)return;
    if(event.data?.type==='scene-style-ready')frame.contentWindow.postMessage({type:'scene-style-context',...packet},location.origin);
    if(event.data?.type==='scene-style-lines'){
      try{
        if(event.data.jobId!==jobId||jobId!==MIX_JOB)throw Error('편집 중인 영상이 바뀌었습니다. 다시 열어 주세요.');
        const response=await fetch('/api/produce/mix/'+encodeURIComponent(jobId)+'/caplines',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({beat_idx:event.data.beatIdx,lines:event.data.lines,reset:event.data.reset})});
        const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'줄 저장 실패');
        const refreshed=await fetch('/api/produce/scene-style/context/'+encodeURIComponent(jobId));const next=await refreshed.json();if(!refreshed.ok)throw Error(next.error||'새 자막을 불러오지 못했습니다.');
        const snapshot=remapSnapshot(event.data.snapshot,packet.context,next.context,event.data.beatIdx),deco={...(STATE.deco||{}),scene_style:snapshot};
        next.context.text={...next.context.text,...snapshot.text};
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
      const deco={...(STATE.deco||{}),scene_style:event.data.snapshot};
      const response=await fetch('/api/produce/mix/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jobId,deco})});
      const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'영상 설정을 저장하지 못했습니다.');
      STATE.deco=deco;packet.snapshot=event.data.snapshot;
      saveWork();status().textContent='문구·효과 적용됨 · 최종 영상에 반영됩니다.';
      frame.contentWindow.postMessage({type:'scene-style-saved',ok:true},location.origin);
    }catch(error){frame.contentWindow.postMessage({type:'scene-style-saved',ok:false,error:error.message},location.origin);}
  });
})();
