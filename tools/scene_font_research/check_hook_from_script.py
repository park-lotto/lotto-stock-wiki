"""훅 제목 = **대본의 제목 줄**인가 — 진짜 앱(격리 DB)으로 잰다 (2026-09-23 사장님 "대본에 있는 제목 훅이 안 들어온다").
  py tools/scene_font_research/check_hook_from_script.py <출력폴더>

재료는 라이브 실물 그대로: job 5638893ae8b7 대본 첫 줄 '제조사도 예상 못한 미친 활용법'(저장된 제목 없음).
  ① 저장된 제목 없음 + AI 후보 있음 → 훅 제목은 **대본 첫 줄**(AI 후보 아님)
  ② 사장님이 직접 정한 제목이 있으면 그게 이긴다
  ③ 대본 첫 줄이 길어 두 줄에 안 담기면 AI 후보로 물러난다(잘린 제목 금지)
  ④ AI 후보가 아예 없으면 긴 줄이라도 대본을 쓴다(빈 제목 금지)
"""
import sys, time, shutil, threading, pathlib, json, urllib.request, urllib.parse
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn

PORT, BASE = 8781, 'http://127.0.0.1:8781'
TITLE = '제조사도 예상 못한 미친 활용법'
TITLE26 = '미국 천재가 만들어 떼돈 번 기발한 제품의 정체'   # 사장님 실물(job 81db354d273e) — 26자라 옛 22자 상한에선 '정체'가 버려졌다
LONG = '젓가락질 못하는 서양인들 위해 나왔다길래 그냥 그런가 보다 했는데 전 세계 SNS에서 난리라는데'
AI = '가루 묻나요?\n이제 끝났죠'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH)
def make(job, first):
    plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                       'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}}
                      for i, c in enumerate([first, '이건 바로 핑거 찹스틱.'])]}
    store.create_mix_job(job, [], 2, 'free'); store.update_mix_job(job, edit_plan=plan)
make('hook-qa', TITLE); make('hook-long', LONG); make('hook-26', TITLE26)
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)

def hook(job, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    d = json.loads(urllib.request.urlopen(f'{BASE}/api/produce/scene-style/context/{job}?{q}').read())
    t = (d.get('context') or {}).get('text') or {}
    return f"{t.get('hook1','')} {t.get('hook2','')}".strip()

h1 = hook('hook-qa', ai_copy=AI)
need(h1 == TITLE, f"① 저장된 제목 없음 → 훅 제목이 대본 첫 줄 '{h1}' — 고치기 전엔 AI 후보('가루 묻나요? 이제 끝났죠')가 들어왔다")
h2 = hook('hook-qa', headcopy_text='내가 정한 제목\n두 번째 줄', ai_copy=AI)
need(h2 == '내가 정한 제목 두 번째 줄', f"② 사장님이 정한 제목이 이긴다 ('{h2}')")
h3 = hook('hook-long', ai_copy=AI)
need(h3 == '가루 묻나요? 이제 끝났죠', f"③ 대본 첫 줄이 길면 AI 후보로 물러난다 ('{h3}')")
h26 = hook('hook-26', ai_copy='손에 묻지 않는 깔끔한' + chr(10) + '과자 먹기')
need(h26.replace(' ', '') == TITLE26.replace(' ', ''),
     f"④ 26자 대본 제목도 낱말 하나 안 버리고 들어온다 '{h26}' — 고치기 전엔 22자 상한에 걸려 AI 후보('손에 묻지 않는 깔끔한 과자 먹기')가 들어왔다")
h4 = hook('hook-long')
need(h4 and h4 != '가루 묻나요? 이제 끝났죠', f"⑥ AI 후보가 없으면 대본을 쓴다(빈 제목 금지) ('{h4}')")
# 5) 진짜 화면: 6단계에서 회색 버튼을 눌러 편집기가 **무엇을 제목으로 그렸나**(사장님이 보는 것).
#    ★진짜 결함은 다리(scene-style-produce.js)가 AI 후보를 headcopy_text 자리에 넣던 것이라, API만 재면 못 잡는다.
from playwright.sync_api import sync_playwright
module.headcopy_gen.suggest = lambda script, family=None, **kw: [{'label': '궁금증', 'text': AI, 'subline': '키보드 쓸 때 필수인 이 도구', 'why': ''}]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
    pg.evaluate("MIX_JOB='hook-qa';PREVIEW_STATUS='ready';STATE.script=" + json.dumps(TITLE + chr(10) + '이건 바로 핑거 찹스틱.') + ";STATE.headcopy=null;window._hcCopies=[];_stepReady=true;cur=3;showPanel()")
    pg.wait_for_timeout(800); pg.evaluate("(()=>{openSceneStyleEditor();return 1})()"); pg.wait_for_timeout(7000)
    fr = next((x for x in pg.frames if 'scene-style-ui-showcase' in x.url), None)
    if fr:
        fr.wait_for_function("window.sceneStyle&&window.sceneStyle.context()", timeout=20000)
        t = fr.evaluate("()=>{const c=window.sceneStyle.context().text;return (c.hook1+' '+c.hook2).trim()}")
    else:
        t = '(편집기 안 열림)'
    need(t == TITLE, "5) 화면에 그려진 훅 제목이 대본 첫 줄 '" + str(t) + "' — 고치기 전엔 '가루 묻나요? 이제 끝났죠'")
    pg.screenshot(path=str(out / 'hook_title.png')); b.close()

print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
