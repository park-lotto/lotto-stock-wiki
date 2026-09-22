"""렌더 뒤 장면꾸미기를 열기만 해도 완성본이 사라지던 것 — 진짜 앱(격리 DB)으로 잰다 (2026-09-22 21:05 실측).
  py tools/scene_font_research/check_reopen_keeps_render.py <출력폴더>

실측: 21:05:46 편집기 열림 → 21:05:56 편집기가 임시저장본을 서버에 자동 저장(mix/settings) → 서버는 deco가 바뀌었다고
완성본 무효화(status done→ready_for_review, video_path None) → 9단계 영상 사라짐, 3단계 재다운로드.
뿌리: '고친 칸만 복원'(v7)이 text를 조각으로 만들어 서버 저장본과 달라졌다. 고침(v8): 서버와 같으면 안 올리고, 올릴 땐 완전한 글로.
  ① 적용한 작업(서버 저장본 있음, status done)을 닫았다 다시 열기만 하면 → 저장 요청 0회, status done·video_path 그대로
  ② 채널명을 고치고 닫았다 열면 → 저장 1회(진짜 편집), 고친 값이 서버 저장본에 완전한 글로 들어간다
"""
import sys, time, shutil, threading, pathlib, json, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
from shopping_shorts import headcopy_gen
import uvicorn
from playwright.sync_api import sync_playwright

JOB, PORT = 'reopen-qa', 8777
BASE = f'http://127.0.0.1:{PORT}'
CANDIDATE = {'label': '궁금증', 'text': '먼지 뭉침을\n싹 없애는 비법', 'subline': '청소가 쉬워지는 이유', 'why': ''}
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
headcopy_gen.suggest = lambda script, family=None, **kw: [dict(CANDIDATE)]
module.headcopy_gen.suggest = headcopy_gen.suggest

tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
caps = ['청소 광인들이 먼지 제거에', '먼지 뭉침을 싹 없애는 비법', '소파 틈새 낀 먼지까지']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH); store.create_mix_job(JOB, [], 3, 'free'); store.update_mix_job(JOB, edit_plan=plan)
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)

def job(): return Store(module.DB_PATH).get_mix_job(JOB)
settings_posts = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.on('request', lambda r: settings_posts.append(r.url) if r.method == 'POST' and '/api/produce/mix/settings' in r.url else None)
    pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
    pg.evaluate(f"MIX_JOB='{JOB}';PREVIEW_STATUS='ready';STATE.script='청소 광인들이 먼지 제거에 목숨 걸게 만든 스펀지.';STATE.headcopy=null;window._hcCopies=[]")
    def open_editor():
        pg.evaluate("(()=>{openSceneStyleEditor();return 1})()"); pg.wait_for_timeout(4000)
        fr = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
        fr.wait_for_function("window.sceneStyle&&window.sceneStyle.context()", timeout=20000); return fr
    def close_editor():
        pg.evaluate("document.querySelector('dialog[open] button').click()"); pg.wait_for_timeout(1500)
    fr = open_editor()
    snap = fr.evaluate('window.sceneStyle.snapshot()')
    # '이 영상에 적용'과 같은 결과를 서버에 직접 만든다(적용한 job) + 렌더가 끝난 상태
    r = urllib.request.urlopen(urllib.request.Request(f'{BASE}/api/produce/mix/settings', data=json.dumps({'job_id': JOB, 'scene_style': snap}).encode('utf-8'), headers={'Content-Type': 'application/json'}))
    need(r.status == 200 and (job().get('deco') or {}).get('scene_style'), '준비: 서버에 꾸미기 저장본이 있는(적용한) 작업')
    close_editor()
    Store(module.DB_PATH).update_mix_job(JOB, status='done', video_path=str(work / 'final.mp4'))
    settings_posts.clear()
    # ① 열기만 하고 닫기
    fr = open_editor(); pg.wait_for_timeout(1500); opened = len(settings_posts)
    close_editor(); pg.wait_for_timeout(800)
    j = job()
    need(opened == 0, f'① 열 때 서버 저장 요청 0회 (실제 {opened}회) — 고치기 전엔 열자마자 1회(조각난 글이 서버와 달라 완성본 무효화)')
    need(j.get('status') == 'done' and j.get('video_path'), f"① 완성본이 그대로 (status {j.get('status')}, video_path {'있음' if j.get('video_path') else '없음'}) — 고치기 전엔 ready_for_review·없음")
    # ② 진짜 편집(채널명)은 저장되고 완전한 글로 들어간다
    fr = open_editor()
    fr.evaluate("()=>{const i=[...document.querySelectorAll('input')].find(e=>e.value==='숏템메이커');i.value='내채널';i.dispatchEvent(new Event('input',{bubbles:true}));}")
    pg.wait_for_timeout(300); settings_posts.clear(); close_editor(); pg.wait_for_timeout(1000)
    fr = open_editor(); pg.wait_for_timeout(1000)
    t = ((job().get('deco') or {}).get('scene_style') or {}).get('text') or {}
    need(t.get('channel') == '내채널' and t.get('hook1'), f"② 고친 채널명이 서버 저장본에 완전한 글과 함께 들어감 (channel {t.get('channel')!r}, hook1 {t.get('hook1')!r})")
    close_editor(); b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
