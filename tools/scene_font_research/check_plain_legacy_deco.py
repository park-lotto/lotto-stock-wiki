"""'원본 영상 그대로'를 고르면 옛 헤드카피·자막 칸이 돌아오나 — 진짜 앱(격리 DB)으로 잰다 (2026-09-24 사장님
 "원본그대로 영상도 자막이나 문구 등 원래 수정할 수 있는 거 아니었어?").

근거: 렌더는 `deco.scene_style`이 없으면 옛 경로(`_burn_captions`가 자막·헤드카피를 태운다)를 탄다
      → 원본 모드에서는 그 옛 칸들이 실제로 결과물에 반영되는 자리다.
  ① 템플릿을 고른 상태: 옛 꾸미기 칸은 숨어 있다(새 편집기가 그리므로 두 벌이 되면 안 된다)
  ② '원본 영상 그대로': 옛 헤드카피 칸(hcText)과 자막 칸(capFont)이 **보인다**
  ③ 다시 템플릿을 고르면 도로 숨는다
"""
import sys, time, shutil, threading, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright

JOB, PORT = 'plain-qa', 8798
BASE = f'http://127.0.0.1:{PORT}'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

tts = work / 'v.wav'; va._run_ffmpeg(['ffmpeg','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','1',str(tts)])
plan = {'beats': [{'beat_idx': i,'t0': i,'dur': 1,'narration': c,'caption_lines': [c],'tts_path': str(tts),'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body','primary': {'video_id':'s0','start':i,'end':i+1}}
                  for i, c in enumerate(['주부들도 감탄한 천재 아이디어','요리할 때마다 기름 튀는 분들'])]}
module.DB_PATH = str(work/'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work/'_thumbs'
store = Store(module.DB_PATH); store.create_mix_job(JOB, [], 2, 'free'); store.update_mix_job(JOB, edit_plan=plan)
store.set_setting('scene_style_inline_enabled', '1')          # 지금 라이브와 같은 상태(전체 공개)
threading.Thread(target=uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning')).run, daemon=True).start()
time.sleep(1.5)

PROBE = """()=>{const vis=id=>{const e=document.getElementById(id);return !!(e&&e.offsetParent!==null)};
  return {헤드카피칸:vis('hcText'), 자막글꼴칸:vis('capFont'), 원본표시:document.querySelector('.panel[data-step="3"]')?.classList.contains('scene-style-plain')}}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width':1500,'height':1000}).new_page()
    pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
    pg.evaluate(f"MIX_JOB='{JOB}';PREVIEW_STATUS='ready';_stepReady=true;cur=3;showPanel()"); pg.wait_for_timeout(9000)
    fr = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
    need(fr is not None, '새 편집기가 6단계에 떴다')
    if fr:
        fr.wait_for_function("window.sceneStyle&&window.sceneStyle.context()", timeout=25000)
        a = pg.evaluate(PROBE); need(not a['헤드카피칸'] and not a['자막글꼴칸'], f'① 템플릿 고른 상태: 옛 칸 숨음 {a}')
        fr.click('[data-none]'); pg.wait_for_timeout(1200)
        c = pg.evaluate(PROBE)
        print('   진단:', pg.evaluate("""()=>{const w=document.querySelector('.panel[data-step=\"3\"] [data-legacy-deco]');
          const t=document.getElementById('hcText'); const out={래퍼:w?getComputedStyle(w).display:'없음'};
          let e=t; const chain=[]; while(e&&e!==document.body){const st=getComputedStyle(e); if(st.display==='none')chain.push((e.id||e.tagName)+':none'); e=e.parentElement;}
          out.숨긴조상=chain.slice(0,4);
          out.패널수=document.querySelectorAll('.panel[data-step=\"3\"]').length;
          out.래퍼부모클래스=w?(w.parentElement.className||'(없음)'):'없음';
          out.래퍼가직계=w?(w.parentElement.matches('.panel[data-step=\"3\"]')):null;
          out.인라인스타일=w?w.getAttribute('style').slice(0,40):null;
          const hits=[];
          for(const sh of document.styleSheets){let rs;try{rs=sh.cssRules}catch(e){continue}
            for(const r of rs){if(!r.selectorText||!r.style||!r.style.display)continue;
              try{if(w.matches(r.selectorText))hits.push(r.selectorText.slice(0,80)+' => '+r.style.display+(r.style.getPropertyPriority('display')?'!':''))}catch(e){}}}
          out.래퍼에걸린규칙=hits;
          return out}"""))
        need(c['헤드카피칸'] or c['자막글꼴칸'], f'② 원본 그대로: 옛 칸이 바로 보인다 {c} — 고치기 전엔 통째로 숨어 있었다')
        pg.click('#decoTabs [data-decotab="copy"]'); pg.wait_for_timeout(600)
        c2 = pg.evaluate(PROBE)
        need(c2['헤드카피칸'], f'② 헤드카피 탭 → 제목 칸 {c2}')
        pg.click('#decoTabs [data-decotab="style"]'); pg.wait_for_timeout(600)
        c3 = pg.evaluate(PROBE)
        need(c3['자막글꼴칸'], f'③ 자막 탭 → 자막 칸 {c3} (탭이라 한 번에 하나씩 보인다)')
        fr.click('[data-p20="0"]'); pg.wait_for_timeout(1200)
        # ★원본 모드에 남는 탭은 실제로 결과물에 들어가는 셋뿐 — 자막·헤드카피·효과. 템플릿은 새 편집기 몫이라 숨긴다.
        fr.click('[data-none]'); pg.wait_for_timeout(1000)
        tabs = pg.evaluate("""()=>[...document.querySelectorAll('#decoTabs [data-decotab]')]
            .filter(b=>b.offsetParent!==null).map(b=>b.dataset.decotab)""")
        need(sorted(tabs) == ['copy','fx','style'], f'④ 원본 모드 탭은 자막·헤드카피·효과 셋 {tabs} (템플릿은 숨김)')
        fr.click('[data-p20="0"]'); pg.wait_for_timeout(1200)
        d = pg.evaluate(PROBE); need(not d['헤드카피칸'], f'⑤ 템플릿 다시 고르면 도로 숨는다 {d}')
        pg.screenshot(path=str(out/'plain_legacy.png'))
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
