"""'원본 영상 그대로'에서 **새 편집기 오른쪽 문구/텍스트 안에** 헤드카피·자막 카드가 뜨고, 고치면 옛 칸에 들어가나 — 진짜 앱(격리 DB)으로 잰다 (2026-09-24 사장님
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

PROBE = """()=>{const vis=e=>!!(e&&e.offsetParent!==null);
  return {옛화면보임:vis(document.getElementById('hcText')),
          원본표시:document.querySelector('.panel[data-step="3"]')?.classList.contains('scene-style-plain')}}"""
CARDS = """()=>{const vis=e=>!!(e&&e.offsetParent!==null);
  const g=k=>document.querySelector('.scene-text-panel > .text-group[data-group="'+k+'"]');
  return {헤드카피카드:vis(g('plainHead')), 자막카드:vis(g('plainCaption')),
          카드제목:[...document.querySelectorAll('.scene-text-panel > .text-group')].filter(vis).map(e=>e.querySelector('summary b').textContent)}}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width':1500,'height':1000}).new_page()
    pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
    pg.evaluate(f"MIX_JOB='{JOB}';PREVIEW_STATUS='ready';_stepReady=true;cur=3;showPanel()"); pg.wait_for_timeout(9000)
    fr = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
    need(fr is not None, '새 편집기가 6단계에 떴다')
    if fr:
        fr.wait_for_function("window.sceneStyle&&window.sceneStyle.context()", timeout=25000)
        a = fr.evaluate(CARDS)
        need(not a['헤드카피카드'] and not a['자막카드'], f'① 템플릿 고른 상태: 헤드카피·자막 카드 없음 {a["카드제목"]}')
        fr.click('[data-none]'); pg.wait_for_timeout(1500)
        c = fr.evaluate(CARDS)
        need(c['헤드카피카드'] and c['자막카드'], f'② 원본 그대로: 오른쪽에 헤드카피·자막 카드가 뜬다 {c["카드제목"]}')
        out_probe = pg.evaluate(PROBE)
        need(not out_probe['옛화면보임'], f'③ 옛 구버전 화면은 안 보인다 {out_probe} — 값만 뒤에서 쓴다')
        fr.evaluate("""()=>{const t=document.querySelector('[data-plain-id="hcText"]');
          t.value='원본에서 쓴 제목';t.dispatchEvent(new Event('input',{bubbles:true}));return 1}""")
        pg.wait_for_timeout(800)
        val = pg.evaluate("()=>document.getElementById('hcText').value")
        need(val == '원본에서 쓴 제목', f'④ 카드에 쓰면 옛 헤드카피 칸에 들어간다 (실제 "{val}")')
        fr.evaluate("""()=>{const t=document.querySelector('[data-plain-id="capOutline"]');
          t.checked=false;t.dispatchEvent(new Event('change',{bubbles:true}));return 1}""")
        pg.wait_for_timeout(600)
        need(pg.evaluate("()=>document.getElementById('capOutline').checked") is False, '④ 자막 외곽선 끄기도 옛 칸에 들어간다')
        fr.click('[data-p20="0"]'); pg.wait_for_timeout(1500)
        d = fr.evaluate(CARDS); need(not d['헤드카피카드'], f'⑤ 템플릿 다시 고르면 카드가 사라진다 {d["카드제목"]}')
        pg.screenshot(path=str(out/'plain_cards.png'))
    b.close()

