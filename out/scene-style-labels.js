(()=>{
 const api=window.sceneStyle,preview=document.querySelector('#a-live-preview');if(!api)return;
 const defaults={watermark:{on:false,text:'@숏템메이커',x:5,y:90,size:3,opacity:65,color:'#ffffff'},ad:{on:false,text:'[광고]',x:5,y:4,size:3,opacity:100,color:'#ffffff'}};
 const section=document.createElement('details');section.className='scene-label-settings';section.open=true;
 section.innerHTML='<summary>워터마크 · 광고 표시 <small>모든 장면</small></summary>';
 for(const [key,title] of [['watermark','워터마크'],['ad','광고 표시']]){
   const row=document.createElement('div');row.dataset.brand=key;
   row.innerHTML=`<label><input type="checkbox" data-brand-field="on"> ${title}</label><div data-brand-options><input type="text" maxlength="40" data-brand-field="text" aria-label="${title} 문구"><label>크기<input type="range" min="1" max="10" step="0.2" data-brand-field="size"></label><label>투명도<input type="range" min="10" max="100" step="1" data-brand-field="opacity"></label><label>색상<input type="color" data-brand-field="color"></label><small>미리보기에서 끌어 위치를 옮기세요.</small></div>`;section.append(row);
 }
 document.querySelector('.scene-effects-panel').prepend(section);
 const layer=document.createElement('div');layer.className='scene-brand-layer';preview.append(layer);
 const config=key=>({...defaults[key],...api.branding()[key]});
 function controls(){section.querySelectorAll('[data-brand]').forEach(row=>{const item=config(row.dataset.brand);row.querySelector('[data-brand-options]').hidden=!item.on;row.querySelectorAll('[data-brand-field]').forEach(input=>{if(input.type==='checkbox')input.checked=item.on;else input.value=item[input.dataset.brandField]})})}
 function draw(){layer.replaceChildren();for(const key of Object.keys(defaults)){const item=config(key);if(!item.on)continue;const el=document.createElement('div');el.className='scene-brand';el.dataset.brandLabel=key;el.textContent=item.text;Object.assign(el.style,{left:item.x+'%',top:item.y+'%',fontSize:preview.clientWidth*item.size/100+'px',opacity:item.opacity/100,color:item.color});layer.append(el)}}
 section.addEventListener('input',event=>{const key=event.target.closest('[data-brand]')?.dataset.brand,field=event.target.dataset.brandField;if(!key||!field)return;const item=config(key);item[field]=event.target.type==='checkbox'?event.target.checked:event.target.type==='range'?Number(event.target.value):event.target.value;api.branding({...api.branding(),[key]:item});controls();draw()});
 let drag=null;
 layer.addEventListener('pointerdown',event=>{const el=event.target.closest('[data-brand-label]');if(!el||event.button!==0)return;drag={key:el.dataset.brandLabel,x:event.clientX,y:event.clientY,item:config(el.dataset.brandLabel),id:event.pointerId};layer.setPointerCapture(event.pointerId);event.preventDefault()});
 layer.addEventListener('pointermove',event=>{if(!drag||event.pointerId!==drag.id)return;const r=preview.getBoundingClientRect(),item={...drag.item};item.x=Math.max(0,Math.min(90,item.x+(event.clientX-drag.x)/r.width*100));item.y=Math.max(0,Math.min(95,item.y+(event.clientY-drag.y)/r.height*100));api.branding({...api.branding(),[drag.key]:item});draw()});
 for(const name of ['pointerup','pointercancel','lostpointercapture'])layer.addEventListener(name,()=>drag=null);
 const caption=document.querySelector('.layout-a [data-field-key="caption"]'),lines=document.createElement('details');lines.className='scene-line-editor';
 lines.innerHTML='<summary>줄 나누기</summary><p>Enter: 여기서 나누기 · 줄 맨 앞 Backspace: 윗줄과 합치기</p><div data-line-inputs></div><div class="scene-line-actions"><button type="button" data-lines-save>이 장면 줄 저장</button><button type="button" data-lines-reset>자동으로</button></div><small data-lines-status></small>';
 caption.append(lines);let lastKey='',pending=false;
 function fillLines(){const context=api.context(),scene=context?.scenes[api.geometry().sceneIndex],input=caption.querySelector('[data-bind="caption"]');const values=scene?context.scenes.filter(s=>s.beat_idx===scene.beat_idx&&s.caption).map(s=>s.caption):input.value.split('\n');const box=lines.querySelector('[data-line-inputs]');box.replaceChildren(...values.map((text,i)=>window.makeCaptionLineInput(text,i)));}
 function sync(){const context=api.context(),index=api.geometry().sceneIndex,key=context?`${context.jobId}:${context.scenes[index]?.beat_idx}`:`local:${api.snapshot().presetId}:${index}`;if(key!==lastKey){lastKey=key;fillLines()}controls();draw()}
 const status=message=>lines.querySelector('[data-lines-status]').textContent=message;
 lines.addEventListener('toggle',()=>{if(lines.open&&!pending)fillLines()});
 lines.addEventListener('click',event=>{const reset=!!event.target.closest('[data-lines-reset]');if(!reset&&!event.target.closest('[data-lines-save]'))return;if(pending)return;const values=[...lines.querySelectorAll('[data-capline]')].map(e=>e.value.trim()).filter(Boolean);if(!reset&&!values.length){status('줄을 입력해 주세요.');return;}const context=api.context();
   if(window.parent!==window&&context){pending=true;status('줄을 저장하는 중…');window.parent.postMessage({type:'scene-style-lines',jobId:context.jobId,beatIdx:context.scenes[api.geometry().sceneIndex].beat_idx,lines:values,reset,snapshot:api.snapshot()},location.origin);}
   else{if(reset)api.resetCaptionText();else{const input=caption.querySelector('[data-bind="caption"]');input.value=values.join('\n');input.dispatchEvent(new Event('input',{bubbles:true}))}document.querySelector('.layout-a .edit-pane > .primary').click();fillLines();status('시안에 저장했습니다. 영상에 연결하면 줄별로 재생됩니다.');}
 });
 addEventListener('message',event=>{if(event.source!==window.parent||event.origin!==location.origin||event.data?.type!=='scene-style-lines-result')return;pending=false;status(event.data.ok?'줄 저장 완료 · 영상에 반영됩니다.':event.data.error||'저장하지 못했습니다.');if(event.data.ok){lastKey='';sync()}});
 new MutationObserver(sync).observe(preview.querySelector('.precision-edit-layer'),{childList:true});addEventListener('resize',()=>{if(!window.sceneStyleExporting)draw()});sync();
})();
