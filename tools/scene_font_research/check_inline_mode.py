"""6단계 새 편집기 인라인 모드(관리자 스위치 scene_style_inline_enabled) — 진짜 앱(격리 DB)으로 잰다 (2026-09-23).
  py tools/scene_font_research/check_inline_mode.py <출력폴더>

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

JOB, PORT = 'inline-qa', 8778
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
with sync_playwright() as p:
    b = p.chromium.launch()
    # ① 기본(끔)
    d = json.loads(urllib.request.urlopen(f'{BASE}/api/produce/scene-style/flags').read())
    need(d.get('inline') is False, f'① 스위치 없음 → flags.inline=false ({d})')
    pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page(); open_page(pg); goto_step6(pg); r = pg.evaluate(PROBE)
    need(r['show'] and not r['hasInline'] and not r['inlineActive'] and r['btnVisible'], f'① 끔: 구버전 UI·회색 버튼 그대로, 인라인 편집기 없음 ({r})')
    pg.screenshot(path=str(out / 'off_step6.png')); pg.close()
    # ② 켬("1")
    Store(module.DB_PATH).set_setting('scene_style_inline_enabled', '1')
    d = json.loads(urllib.request.urlopen(f'{BASE}/api/produce/scene-style/flags').read())
    need(d.get('inline') is True, f'② 스위치 "1" → flags.inline=true ({d})')
    pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page(); open_page(pg)
    r0 = pg.evaluate(PROBE); need(not r0['show'] and not r0['iframeSrc'], f'② 6단계 전엔 편집기를 안 연다(구버전 숨김 표시는 미리 붙어도 패널이 안 보인다) ({r0})')
    goto_step6(pg); r = pg.evaluate(PROBE); fr = editor_frame(pg)
    need(r['show'] and r['hasInline'] and r['inlineActive'] and r['iframeSrc'] and not r['btnVisible'] and not r['dialogOpen'], f'② 6단계에 오면 새 편집기가 패널 안에 바로, 구버전 UI·버튼 숨김, 팝업 없음 ({r})')
    need(fr is not None and fr.evaluate("window.sceneStyle.context().jobId") == JOB, f'② 인라인 편집기가 이 작업 컨텍스트를 실었다 (jobId {fr and fr.evaluate("window.sceneStyle.context().jobId")})')
    hooks = fr.evaluate("()=>[...document.querySelectorAll('#a-live-preview .precision-text')].map(e=>e.dataset.editBind)") if fr else []
    need('hook1' in hooks or 'bodyTitle' in hooks, f'② 편집기가 장면을 그렸다 (텍스트 {hooks})')
    pg.screenshot(path=str(out / 'on_step6.png'))
    # ③ 떠났다 돌아오기
    pg.evaluate("cur=4;showPanel()"); pg.wait_for_timeout(1200)
    draft = pg.evaluate(f"localStorage.getItem('scene-style-draft:{JOB}')")
    r2 = pg.evaluate(PROBE); need(not r2['show'] and draft, f'③ 6단계를 떠나면 임시저장본이 남는다 (draft {"있음" if draft else "없음"})')
    goto_step6(pg); r3 = pg.evaluate(PROBE); fr2 = editor_frame(pg)
    need(r3['inlineActive'] and fr2 is not None and fr2.evaluate("window.sceneStyle.context().jobId") == JOB, f'③ 다시 오면 다시 열린다 ({r3["inlineActive"]})')
    pg.close()
    # ④ 2026-09-26 사장님 "장면꾸미기를 누르면 구버전이 나오고 신버전 편집을 눌러야 넘어간다":
    #   제목 후보(AI)가 느리면 그동안 구버전 UI·회색 버튼이 보였다 → 6단계에 오자마자(1초 안) 구버전은 숨어 있어야 한다.
    import time as _t
    _fast = module.headcopy_gen.suggest
    def _slow(*a, **k): _t.sleep(6); return _fast(*a, **k)
    module.headcopy_gen.suggest = _slow
    pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page(); open_page(pg)
    pg.evaluate("cur=3;showPanel()"); pg.wait_for_timeout(800); r4 = pg.evaluate(PROBE)
    need(r4['inlineActive'] and not r4['btnVisible'], f'④ 제목 후보가 느려도 6단계에 오자마자 구버전·회색 버튼은 숨김 ({r4})')
    pg.screenshot(path=str(out / 'slow_step6.png'))
    fr4 = None
    for _ in range(20):
        fr4 = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
        if fr4: break
        pg.wait_for_timeout(1000)
    need(fr4 is not None, '④ 느려도 결국 새 편집기가 열린다')
    module.headcopy_gen.suggest = _fast
    pg.close()
    # ⑤ 장면 불러오기가 실패해도 구버전으로 떨어지지 않고, 새 편집기 자리에 이유 + [다시 시도]가 나온다
    pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.route('**/api/produce/scene-style/context/**', lambda route: route.fulfill(status=500, body='{"ok":false,"error":"장면을 불러오지 못했습니다(시험)"}', content_type='application/json'))
    open_page(pg); goto_step6(pg); r5 = pg.evaluate(PROBE)
    note5 = pg.evaluate("document.getElementById('sceneStyleInlineStatus')?.innerText||''")
    retry5 = pg.evaluate("!!document.querySelector('#sceneStyleInline button[data-retry]')")
    need(r5['inlineActive'] and not r5['btnVisible'] and '시험' in note5 and retry5, f'⑤ 불러오기 실패 → 구버전 안 나옴, 이유·다시 시도 표시 ({r5}, note={note5!r}, retry={retry5})')
    pg.unroute('**/api/produce/scene-style/context/**')
    if retry5:
        pg.click('#sceneStyleInline button[data-retry]'); pg.wait_for_timeout(3000)
        print('   ⑤ 다시시도 뒤 안내:', pg.evaluate("document.getElementById('sceneStyleInlineStatus')?.innerText"), pg.evaluate(PROBE))
        fr5 = editor_frame(pg)
        need(fr5 is not None and fr5.evaluate("window.sceneStyle.context().jobId") == JOB, '⑤ [다시 시도]를 누르면 새 편집기가 열린다')
    pg.screenshot(path=str(out / 'fail_step6.png')); pg.close();
    # ⑥ 사장님 job 65358b12dd6e 실측: 6단계가 **작업번호(MIX_JOB)보다 먼저** 보이면 편집기 요청이 한 번도 안 나갔다
    #   → 구버전+회색 버튼이 남고 버튼을 눌러야 열렸다. 작업번호가 늦게 와도 스스로 열려야 하고, 그 사이 구버전은 숨어야 한다.
    pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
    pg.evaluate(STATE_JS.replace(f"MIX_JOB='{JOB}'", "MIX_JOB=''")); pg.evaluate("cur=3;showPanel()"); pg.wait_for_timeout(1500)
    r6a = pg.evaluate(PROBE)
    need(r6a['inlineActive'] and not r6a['btnVisible'], f'⑥ 작업번호 전: 구버전·회색 버튼 숨김 ({r6a})')
    pg.evaluate(f"MIX_JOB='{JOB}'"); pg.wait_for_timeout(2500)
    fr6 = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
    if fr6: fr6.wait_for_function("window.sceneStyle&&window.sceneStyle.context()", timeout=20000)
    need(fr6 is not None and fr6.evaluate("window.sceneStyle.context().jobId") == JOB, '⑥ 작업번호가 늦게 와도 누르지 않고 새 편집기가 스스로 열린다')
    pg.screenshot(path=str(out / 'late_job_step6.png')); pg.close(); b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
