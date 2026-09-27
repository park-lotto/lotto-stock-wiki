# -*- coding: utf-8 -*-
"""6단계(장면꾸미기)를 적용 없이 떠날 때 "이 템플릿으로 진행할까요?" — 진짜 앱(격리 DB)·진짜 브라우저로 누른다.
  ../../.venv/Scripts/python.exe tools/scene_font_research/check_leave_gate.py <출력폴더> [--inline]
  --inline = 라이브와 같은 인라인 모드(6단계 패널 안 편집기, 스위치 scene_style_inline_enabled=1). 없으면 팝업 모드.

2026-09-26 사장님: 고객 조율가님(job 7cfa8bd7a23e)이 템플릿을 꾸며 두고 [이 영상에 적용] 없이 넘어가
scene_style=None → 썸네일·영상에 템플릿이 안 들어갔다. 자동 저장은 09-16 사고(열어만 봐도 t11 저장)라 **묻는다**.

  ① 적용 안 한 job에서 [다음 →] → 확인창이 뜨고 아직 6단계, DB 저장 없음      (고치기 전: 창 없이 7단계로 감)
  ② [계속 꾸미기] → 창 닫히고 6단계 그대로
  ③ [템플릿 없이 진행] → 7단계, DB scene_style 여전히 없음(종전 동작)
  ④ 6단계로 돌아와 [다음 →] → 다시 묻는다 → [이 템플릿으로 진행] → DB에 템플릿 저장 + 7단계
  ⑤ 적용된 뒤엔 오가도 안 묻는다
  ⑥ 편집기 [썸네일 단계로 이동](새 job) → 창이 뜨고 [이 템플릿으로 진행] → 저장 + 7단계
  ⑦ 뒤로 가는 길(6→5단계)은 안 묻는다
"""
import sys, json, time, shutil, threading, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright

JOBS, PORT = ['leave-gate-a', 'leave-gate-b'], 8781
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

source = work / 'source.mp4'
va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=540x960:d=1', '-f', 'lavfi', '-i', 'color=c=green:s=540x960:d=1', '-f', 'lavfi', '-i', 'color=c=blue:s=540x960:d=1',
                '-filter_complex', '[0][1][2]concat=n=3:v=1:a=0', '-r', '30', '-pix_fmt', 'yuv420p', str(source)])
tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
caps = ['첫 번째 실제 자막', '두 번째 실제 자막', '마지막 실제 자막']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH)
INLINE = '--inline' in sys.argv
if INLINE: store.set_setting('scene_style_inline_enabled', '1')
print('  모드:', '인라인' if INLINE else '팝업')
for j in JOBS:
    (work / j / 's0').mkdir(parents=True); shutil.copyfile(source, work / j / 's0' / 'source.mp4')
    store.create_mix_job(j, [], 3, 'free'); store.update_mix_job(j, edit_plan=plan)
def saved(j):
    return ((Store(module.DB_PATH).get_mix_job(j).get('deco') or {}).get('scene_style') or {}).get('presetId')

server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(100):
    if server.started: break
    time.sleep(.2)
BASE = f'http://127.0.0.1:{PORT}'
ASK = "!!document.getElementById('sceneStyleLeaveAsk')"
STATE = "({cur:cur,deco:PANEL_BY_KEY.deco,thumb:PANEL_BY_KEY.thumb})"

def open_editor(pg, job):
    pg.evaluate(f"MIX_JOB='{job}';PREVIEW_STATUS='ready';cur=PANEL_BY_KEY.deco;renderSteps();showPanel()")
    pg.evaluate('openSceneStyleEditor()'); pg.wait_for_timeout(3000)
    fr = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
    fr.wait_for_function('window.sceneStyle&&window.sceneStyle.context()&&window.sceneStyle.context().jobId', timeout=30000)
    return fr

try:
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        pg = b.new_page(viewport={'width': 1600, 'height': 1200}); pg.on('pageerror', lambda e: errs.append(str(e)))
        dialogs = []; pg.on('dialog', lambda d: (dialogs.append(d.message), d.dismiss()))
        pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
        A, B2 = JOBS
        fr = open_editor(pg, A)
        preset = fr.evaluate('window.sceneStyle.snapshot()&&window.sceneStyle.snapshot().presetId')
        print('  편집기 화면 템플릿:', preset)
        pg.evaluate("document.querySelector('dialog[open] button')?.click()"); pg.wait_for_timeout(800)   # [저장하고 닫기] — 적용 안 한 job이라 저장 안 됨(종전)
        need(saved(A) is None, f'준비: 적용 안 하고 닫으면 서버 저장 없음 ({saved(A)})')
        # ①
        pg.evaluate('go(1)'); pg.wait_for_timeout(500); st = pg.evaluate(STATE)
        need(pg.evaluate(ASK) and st['cur'] == st['deco'] and saved(A) is None, f'① [다음]에 확인창이 뜨고 6단계에 머문다, 저장 없음 ({st}, 창 {pg.evaluate(ASK)})')
        if pg.evaluate(ASK): pg.screenshot(path=str(out / 'leave_ask.png'))
        # ②
        if pg.evaluate(ASK):
            pg.click('[data-leave="stay"]'); pg.wait_for_timeout(300); st = pg.evaluate(STATE)
            need(not pg.evaluate(ASK) and st['cur'] == st['deco'], f'② [계속 꾸미기] → 창 닫힘·6단계 그대로 ({st})')
        # ③
        pg.evaluate('go(1)'); pg.wait_for_timeout(400)
        if pg.evaluate(ASK):
            pg.click('[data-leave="skip"]'); pg.wait_for_timeout(800)
        st = pg.evaluate(STATE)
        need(st['cur'] == st['thumb'] and saved(A) is None, f'③ [템플릿 없이 진행] → 7단계, 저장 없음 ({st}, {saved(A)})')
        # ⑦ 뒤로는 안 묻는다 — 6단계로 돌아와서 5단계로
        pg.evaluate('jump(PANEL_TO_ORB[PANEL_BY_KEY.deco])'); pg.wait_for_timeout(400)
        pg.evaluate('go(-1)'); pg.wait_for_timeout(400); st = pg.evaluate(STATE)
        need(not pg.evaluate(ASK) and st['cur'] != st['deco'], f'⑦ 뒤로 가는 길은 안 묻는다 ({st})')
        # ④
        pg.evaluate('jump(PANEL_TO_ORB[PANEL_BY_KEY.deco])'); pg.wait_for_timeout(400)
        pg.evaluate('go(1)'); pg.wait_for_timeout(400)
        asked = pg.evaluate(ASK)
        if asked:
            pg.click('[data-leave="apply"]'); pg.wait_for_function('!document.getElementById("sceneStyleLeaveAsk")', timeout=20000); pg.wait_for_timeout(500)
        st = pg.evaluate(STATE)
        need(asked and st['cur'] == st['thumb'] and saved(A) == preset, f'④ 다시 묻고 [이 템플릿으로 진행] → 서버에 {preset} 저장 + 7단계 ({st}, 저장 {saved(A)})')
        # ⑤
        pg.evaluate('jump(PANEL_TO_ORB[PANEL_BY_KEY.deco])'); pg.wait_for_timeout(400); pg.evaluate('go(1)'); pg.wait_for_timeout(500); st = pg.evaluate(STATE)
        need(not pg.evaluate(ASK) and st['cur'] == st['thumb'], f'⑤ 적용된 뒤엔 안 묻고 넘어간다 ({st})')
        # ⑥ 편집기 [썸네일 단계로 이동] 경로(새 job)
        fr = open_editor(pg, B2)
        fr.evaluate('window.sceneStyle.show(1)'); fr.click('[data-thumb-pin]')
        fr.wait_for_function("document.querySelector('[data-thumb-msg]').textContent.startsWith('✓')", timeout=60000)
        fr.click('[data-thumb-go]'); pg.wait_for_timeout(2500)
        asked = pg.evaluate(ASK)
        if asked:
            pg.click('[data-leave="apply"]'); pg.wait_for_function('!document.getElementById("sceneStyleLeaveAsk")', timeout=20000); pg.wait_for_timeout(500)
        st = pg.evaluate(STATE)
        need(asked and st['cur'] == st['thumb'] and saved(B2) == preset, f'⑥ [썸네일 단계로 이동]에도 묻고 적용 → 저장 + 7단계 ({st}, 저장 {saved(B2)})')
        pg.screenshot(path=str(out / 'after_apply_thumb.png'))
        need(not dialogs, f'브라우저 기본 확인창(confirm/alert)을 안 쓴다 {dialogs}')
        need(not errs, f'페이지 오류 {errs[:4]}'); b.close()
finally:
    server.should_exit = True; time.sleep(1)
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
