(()=>{
 const api=window.sceneStyle,preview=document.querySelector('#a-live-preview');if(!api)return;
 const defaults={watermark:{on:false,text:'@숏템메이커',x:50,y:90,size:3,opacity:65,color:'#ffffff',align:'center',motion:'none'},ad:{on:false,text:'[광고]',x:87,y:6,size:3,opacity:100,color:'#ffffff'}};
 const section=document.createElement('details');section.className='scene-label-settings';section.open=true;
 section.innerHTML='<summary>워터마크 · 광고 표시</summary><small>설정은 자동으로 기억합니다.</small>';
 for(const [key,title] of [['watermark','워터마크'],['ad','광고 표시']]){
   const row=document.createElement('div');row.dataset.brand=key;
   row.innerHTML=`<label class="brand-toggle"><input type="checkbox" data-brand-field="on"><span>${title}</span></label><div data-brand-options><input type="text" maxlength="40" data-brand-field="text" aria-label="${title} 문구"><details><summary>크기 · 색상</summary><label>크기<input type="range" min="1" max="10" step="0.2" data-brand-field="size"></label><label>투명도<input type="range" min="10" max="100" step="1" data-brand-field="opacity"></label><label>색상<input type="color" data-brand-field="color"></label></details><button type="button" data-brand-reset>기본 위치로</button></div>`;section.append(row);
 }
 document.querySelector('.scene-effects-panel').prepend(section);
 const layer=document.createElement('div');layer.className='scene-brand-layer';preview.append(layer);
 const config=key=>{const saved=api.branding()[key],item={...defaults[key],...saved};if(key==='watermark'&&saved&&!saved.align){if(saved.x===36)item.x=50;else item.align='left';}return item;};
 const motionControl=document.createElement('label');motionControl.innerHTML='움직임<select data-brand-field="motion"><option value="none">없음</option><option value="float">살짝 움직임</option></select>';section.querySelector('[data-brand="watermark"] [data-brand-options]').append(motionControl);
 section.addEventListener('click',event=>{if(!event.target.closest('[data-brand-reset]'))return;const key=event.target.closest('[data-brand]').dataset.brand,item=config(key);api.branding({...api.branding(),[key]:{...item,x:defaults[key].x,y:defaults[key].y,...(key==='watermark'?{align:'center'}:{})}});controls();draw();});
 function controls(){section.querySelectorAll('[data-brand]').forEach(row=>{const item=config(row.dataset.brand);row.querySelector('[data-brand-options]').hidden=!item.on;row.querySelectorAll('[data-brand-field]').forEach(input=>{if(input.type==='checkbox')input.checked=item.on;else input.value=item[input.dataset.brandField]})})}
 function draw(){layer.replaceChildren();for(const key of Object.keys(defaults)){const item=config(key);if(!item.on)continue;const el=document.createElement('div');el.className='scene-brand';el.dataset.brandLabel=key;const ink=document.createElement('span');ink.className='scene-brand-ink';ink.style.display='block';ink.textContent=item.text;el.append(ink);Object.assign(el.style,{left:item.x+'%',top:item.y+'%',fontSize:preview.clientWidth*item.size/100+'px',opacity:item.opacity/100,color:item.color,transform:item.align==='center'?'translateX(-50%)':'none'});layer.append(el);if(item.motion==='float'){const distance=preview.clientWidth*.012;ink.animate([{transform:'translateY(0)'},{transform:`translateY(${-distance}px)`},{transform:'translateY(0)'}],{duration:2400,iterations:Infinity,easing:'ease-in-out'});}}}
 window.sceneBranding={motionAt(time){let moving=false;layer.querySelectorAll('.scene-brand-ink').forEach(el=>el.getAnimations().forEach(a=>{a.pause();a.currentTime=time;moving=true}));return moving}};
 section.addEventListener('input',event=>{const key=event.target.closest('[data-brand]')?.dataset.brand,field=event.target.dataset.brandField;if(!key||!field)return;const item=config(key);item[field]=event.target.type==='checkbox'?event.target.checked:event.target.type==='range'?Number(event.target.value):event.target.value;api.branding({...api.branding(),[key]:item});controls();draw()});
 let drag=null;
 layer.addEventListener('pointerdown',event=>{const el=event.target.closest('[data-brand-label]');if(!el||event.button!==0)return;drag={key:el.dataset.brandLabel,x:event.clientX,y:event.clientY,item:config(el.dataset.brandLabel),id:event.pointerId};layer.setPointerCapture(event.pointerId);event.preventDefault()});
 layer.addEventListener('pointermove',event=>{if(!drag||event.pointerId!==drag.id)return;const r=preview.getBoundingClientRect(),item={...drag.item};item.x=Math.max(0,Math.min(90,item.x+(event.clientX-drag.x)/r.width*100));item.y=Math.max(0,Math.min(95,item.y+(event.clientY-drag.y)/r.height*100));api.branding({...api.branding(),[drag.key]:item});draw()});
 for(const name of ['pointerup','pointercancel','lostpointercapture'])layer.addEventListener(name,()=>drag=null);
 const caption=document.querySelector('.layout-a [data-field-key="caption"]'),lines=document.createElement('details');lines.className='scene-line-editor';
 lines.open=false;
 lines.innerHTML='<summary>자막 나누기</summary><small data-lines-context></small><p>끊을 곳을 누르고 ‘나누기’를 누르세요.</p><div data-line-inputs></div><div class="scene-line-actions"><button type="button" data-lines-split>나누기</button><button type="button" data-lines-merge>윗줄과 합치기</button></div><div class="scene-line-actions"><button type="button" data-lines-save>적용</button><button type="button" data-lines-reset>원래대로</button></div><small data-lines-status></small>';
 let focusedLine=null;
 lines.addEventListener('focusin',event=>{if(event.target.matches('[data-capline]'))focusedLine=event.target;});
 lines.addEventListener('pointerdown',event=>{if(event.target.closest('[data-lines-split],[data-lines-merge]'))event.preventDefault();});
 lines.addEventListener('click',event=>{
   const split=event.target.closest('[data-lines-split]'),merge=event.target.closest('[data-lines-merge]');if(!split&&!merge)return;
   if(!focusedLine?.isConnected){status('먼저 자막에서 끊을 곳을 눌러 주세요.');return;}
   if(merge)focusedLine.setSelectionRange(0,0);
   focusedLine.dispatchEvent(new KeyboardEvent('keydown',{key:split?'Enter':'Backspace',bubbles:true,cancelable:true}));
 });
 caption.after(lines);let lastKey='',pending=false;
 function fillLines(){const context=api.context(),scene=context?.scenes[api.geometry().sceneIndex],input=caption.querySelector('[data-bind="caption"]');const values=scene?context.scenes.filter(s=>s.beat_idx===scene.beat_idx&&s.caption).map(s=>s.caption):input.value.split('\n');const box=lines.querySelector('[data-line-inputs]');box.replaceChildren(...values.map((text,i)=>window.makeCaptionLineInput(text,i)));}
 function sync(){const context=api.context(),index=api.geometry().sceneIndex,key=context?`${context.jobId}:${context.scenes[index]?.beat_idx}`:`local:${api.snapshot()?.presetId||"none"}:${index}`;lines.hidden=!context&&caption.hidden;lines.querySelector('[data-lines-context]').textContent=context?'':'샘플 자막';if(key!==lastKey){lastKey=key;fillLines()}controls();draw()}
 const status=message=>lines.querySelector('[data-lines-status]').textContent=message;
 lines.addEventListener('toggle',()=>{if(lines.open&&!pending)fillLines()});
 lines.addEventListener('click',event=>{const reset=!!event.target.closest('[data-lines-reset]');if(!reset&&!event.target.closest('[data-lines-save]'))return;if(pending)return;const values=[...lines.querySelectorAll('[data-capline]')].map(e=>e.value.trim()).filter(Boolean);if(!reset&&!values.length){status('줄을 입력해 주세요.');return;}const context=api.context();
   if(window.parent!==window&&context){pending=true;status('줄을 저장하는 중…');window.parent.postMessage({type:'scene-style-lines',jobId:context.jobId,beatIdx:context.scenes[api.geometry().sceneIndex].beat_idx,lines:values,reset,snapshot:api.snapshot()},location.origin);}
   else{if(reset)api.resetCaptionText();else{const input=caption.querySelector('[data-bind="caption"]');input.value=values.join('\n');input.dispatchEvent(new Event('input',{bubbles:true}))}document.querySelector('.layout-a .edit-pane > .primary').click();fillLines();status('적용했어요.');}
 });
 addEventListener('message',event=>{if(event.source!==window.parent||event.origin!==location.origin||event.data?.type!=='scene-style-lines-result')return;pending=false;status(event.data.ok?'줄 저장 완료 · 영상에 반영됩니다.':event.data.error||'저장하지 못했습니다.');if(event.data.ok){lastKey='';sync()}});
 new MutationObserver(sync).observe(preview.querySelector('.precision-edit-layer'),{childList:true});addEventListener('resize',()=>{if(!window.sceneStyleExporting)draw()});sync();
})();
