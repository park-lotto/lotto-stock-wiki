"""성우 담기 버튼·샘플 없는 ▶ 점검(2026-10-19 Park님). 사용: py tools/voice_adopt_btn_check.py
① 타입캐스트 '이 성우로' 성공 뒤 버튼이 '✓ 담음'으로 바뀐다(전엔 '등록 중…'에 멈춤)
② 샘플 없는 카드·즐겨찾기 ▶가 꺼져 있지 않고, 누르면 그 성우를 고르고 안내한다"""
import os
from playwright.sync_api import sync_playwright
f = os.path.abspath("shopping_shorts/static/produce.html").replace("\\", "/")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file:///" + f); pg.wait_for_timeout(1500)
    r = pg.evaluate("""async()=>{
      const out={}; const toasts=[]; window.toast=m=>toasts.push(m);
      let picked=null; window.pickPreset=g=>{picked=g};
      window.loadPresets=async()=>{};
      window.fetch=async()=>({json:async()=>({ok:true,group_id:'tcv-x'})});
      TCMINE_RESULTS=[{voice_id:'uc_1',name:'Hanyoung',model:'ssfm-v21'}];
      const btn=document.createElement('button'); btn.textContent='이 성우로'; document.body.appendChild(btn);
      await tcvUse(btn,0,'mine'); out.btn=btn.textContent;
      VOICE_GROUPS=[{group_id:'tcv-x',name:'Hanyoung',engine:'typecast',default_variant:'stable',
        variants:{stable:{sample_url:''}}}];
      VOICE_FAVS=new Set(['tcv-x']);
      let box=document.getElementById('presetCards'); if(!box){box=document.createElement('div');box.id='presetCards';document.body.appendChild(box);}
      try{renderPresetCards();}catch(e){out.renderErr=String(e)}
      const vp=[...document.querySelectorAll('#presetCards .vplay, #presetCards .fplay')];
      out.plays=vp.map(b=>b.disabled);
      if(vp[0]){vp[0].click();} out.picked=picked; out.toast=toasts.slice(-1)[0];
      return out;}""")
    print(r, "errors", errs[:3]); b.close()
