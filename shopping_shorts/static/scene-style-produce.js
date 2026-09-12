(()=>{
  let dialog,frame,jobId,packet;
  const status=()=>document.getElementById('sceneStyleStatus');
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
