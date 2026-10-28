"""인라인 모드 × 관리자 시험 모드(canary) 충돌 — 진짜 앱(격리 DB) (2026-09-25 사고).
  py tools/scene_font_research/check_inline_canary.py <출력폴더>
  사고: canary가 켜진 브라우저(사장님)에서 인라인을 켜면 두 숨김 규칙이 서로의 칸을 숨겨 6단계가 제목만 남았다.
  고치기 전 코드: ① 에서 보이는 칸이 [H3]뿐 → 실패(실측).

(아래는 check_inline_mode의 설명)

사장님: "구버전에서 신버전으로 바꾸는 작업을 유튜브 라이브 방송 이후에 할 건데 바로 교체되게 기본 세팅 먼저".
  ① 스위치 꺼짐(기본): 6단계에 구버전 UI + 회색 버튼 그대로, 인라인 편집기 없음, flags.inline=false
  ② 스위치 "1": 6단계 패널이 보이면 새 편집기가 패널 안에 바로 뜨고(컨텍스트 로드), 구버전 UI·회색 버튼은 숨김
  ③ 6단계를 떠나면 임시저장본이 남고(inlineOpen 해제), 다시 오면 다시 열린다
"""
import sys, time, shutil, threading, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
from shopping_shorts import headcopy_gen
import uvicorn
from playwright.sync_api import sync_playwright

JOB, PORT = 'inline-qa', 8779
BASE = f'http://127.0.0.1:{PORT}'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
headcopy_gen.suggest = lambda script, family=None, **kw: [{'label': '궁금증', 'text': '먼지 뭉침을\n싹 없애는 비법', 'subline': '청소가 쉬워지는 이유', 'why': ''}]
module.headcopy_gen.suggest = headcopy_gen.suggest

tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
caps = ['청소 광인들이 먼지 제거에', '먼지 뭉침을 싹 없애는 비법', '소파 틈새 낀 먼지까지']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH); store.create_mix_job(JOB, [], 3, 'free'); store.update_mix_job(JOB, edit_plan=plan)
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)

STATE_JS = f"MIX_JOB='{JOB}';PREVIEW_STATUS='ready';STATE.script='청소 광인들이 먼지 제거에 목숨 걸게 만든 스펀지.';STATE.headcopy=null;window._hcCopies=[];_stepReady=true"
PROBE = """()=>{const panel=document.querySelector('.panel[data-step="3"]');const inline=document.getElementById('sceneStyleInline');const btn=panel.querySelector('button.btn[onclick="openSceneStyleEditor()"]');
  const fr=inline?inline.querySelector('iframe'):null;return {show:panel.classList.contains('show'),inlineActive:panel.classList.contains('scene-style-inline-active'),hasInline:!!inline,
  iframeSrc:fr?fr.getAttribute('src'):null,btnVisible:!!(btn&&btn.offsetParent!==null),dialogOpen:!!document.querySelector('dialog[open]')}}"""
def open_page(pg):
    pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500); pg.evaluate(STATE_JS)
def goto_step6(pg):
    pg.evaluate("cur=3;showPanel()"); pg.wait_for_timeout(2500)
def editor_frame(pg):
    fr = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
    if fr: fr.wait_for_function("window.sceneStyle&&window.sceneStyle.context()", timeout=20000)
    return fr

import urllib.request, json
PROBE2 = """()=>{const panel=document.querySelector('.panel[data-step="3"]');
  const kids=[...panel.children].filter(e=>e.offsetParent!==null&&e.getBoundingClientRect().height>0).map(e=>e.tagName+'#'+(e.id||''));
  return {cls:panel.className,kids,inline:!!document.getElementById('sceneStyleInline')?.offsetParent,canary:!!document.getElementById('sceneStyleCanary')?.offsetParent}}"""
def run(b, canary):
    ctx = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = ctx.new_page()
    if canary: ctx.add_init_script("localStorage.setItem('scene-style-canary-enabled','1')")
    else: ctx.add_init_script("localStorage.removeItem('scene-style-canary-enabled')")
    open_page(pg); goto_step6(pg); pg.wait_for_timeout(3000); r = pg.evaluate(PROBE2); return ctx, pg, r
with sync_playwright() as p:
    b = p.chromium.launch()
    Store(module.DB_PATH).set_setting('scene_style_inline_enabled', '1')
    ctx, pg, r = run(b, True); fr = editor_frame(pg) if r['inline'] else None
    need(r['inline'] and 'SECTION#sceneStyleInline' in r['kids'] and not r['canary'], f'① canary 켠 브라우저 + 인라인 켬 → 새 편집기가 보인다 {r}')
    need(fr is not None and fr.evaluate("window.sceneStyle.context().jobId") == JOB, '① 그 편집기가 작업을 실었다')
    pg.screenshot(path=str(out / 'canary_inline.png')); ctx.close()
    ctx, pg, r = run(b, False)
    need(r['inline'] and not r['canary'], f'② canary 없는 브라우저 + 인라인 켬 → 새 편집기 {r}'); ctx.close()
    Store(module.DB_PATH).set_setting('scene_style_inline_enabled', '')
    ctx, pg, r = run(b, True)
    need(r['canary'] and 'scene-style-canary-active' in r['cls'] and not r['inline'], f'③ 인라인 끔 + canary 켬 → canary(관리자 시험)는 종전대로 {r}'); ctx.close()
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
