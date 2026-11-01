"""썸네일 글자 손잡이 크기 드래그 점검(2026-10-18 고객 제보). 사용: py tools/thumb_handle_check.py <produce.html 절대경로>
고치기 전엔 크기가 2로 붙어 안 움직였다. 정상이면 키움>살짝끔, 줄임<키움, 다시키움>줄임."""
import sys
from playwright.sync_api import sync_playwright
f=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1400,'height':1000})
    pg.on('pageerror', lambda e: None)
    pg.goto('file:///'+f)
    r=pg.evaluate("""()=>{
      const box=document.getElementById('thumbHandles'); const cv=document.getElementById('thumbCanvas');
      if(!box||!cv) return 'no elems';
      // 보이게 만든다
      let el=box; while(el){ if(el.style) el.style.display=''; el=el.parentElement; }
      document.body.appendChild(box); box.style.cssText='position:fixed;left:100px;top:100px;width:360px;height:640px';
      THUMB_STATE.layers=[{text:'모래로 끓여 봤다',x:0.5,y:0.3,rot:0}]; THUMB_STATE.sel=0;
      try{initThumbHandleDrag();}catch(e){return 'init err '+e}
      renderThumbHandles();
      const h=box.querySelector('button[data-h=size]'); if(!h) return 'no handle';
      const r=h.getBoundingClientRect(); const x=r.left+r.width/2,y=r.top+r.height/2;
      const ev=(t,x,y,tg)=>(tg||document).dispatchEvent(new MouseEvent(t,{clientX:x,clientY:y,bubbles:true,cancelable:true}));
      const out=[JSON.stringify(box.getBoundingClientRect()), getComputedStyle(box).pointerEvents];
      h.dispatchEvent(new MouseEvent('mousedown',{clientX:x,clientY:y,bubbles:true,cancelable:true}));
      ev('mousemove',x+2,y+2); out.push('살짝끔='+THUMB_STATE.layers[0].size);
      ev('mousemove',x+60,y+60); out.push('키움='+THUMB_STATE.layers[0].size); ev('mouseup',x+60,y+60);
      const h2=box.querySelector('button[data-h=size]').getBoundingClientRect();
      const x2=h2.left+h2.width/2,y2=h2.top+h2.height/2;
      box.querySelector('button[data-h=size]').dispatchEvent(new MouseEvent('mousedown',{clientX:x2,clientY:y2,bubbles:true,cancelable:true}));
      ev('mousemove',x2-80,y2-80); out.push('줄임='+THUMB_STATE.layers[0].size);
      ev('mousemove',x2+40,y2+40); out.push('다시키움='+THUMB_STATE.layers[0].size); ev('mouseup',0,0);
      out.push('범위='+JSON.stringify(_thumbSizeRange(THUMB_STATE.layers[0])));
      return out.join(' | ');
    }""")
    print(r); b.close()
