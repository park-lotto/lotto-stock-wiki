"""회색 버튼을 제목 후보보다 먼저 눌러도 대본 기반 제목이 들어가는지 — 진짜 앱(격리 DB)으로 잰다 (2026-09-22).
  py tools/scene_font_research/check_headcopy_wait.py <출력폴더>

라이브 저널 실측: 컨텍스트 17:15:28 `headcopy_text=`(빈칸) → 후보 17:15:32 도착. 후보보다 먼저 누르면 서버가
대본 첫 문장을 제목에 넣어 12/10자·23/22자로 넘쳤다(사장님 화면).
여기서는 AI 호출(headcopy_gen.suggest)만 3초 걸리는 가짜로 바꾸고(외부 API 없음), 나머지는 진짜 앱·진짜 제작소 페이지.
  ① 6단계 진입 직후(후보 도착 전) 회색 버튼 → 편집기 컨텍스트 요청의 headcopy_text가 후보 1번이어야 한다
  ② 진입 자동 생성 + 편집기 대기가 겹쳐도 /headcopy/suggest 호출은 1회
"""
import sys, time, shutil, threading, pathlib, urllib.parse
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
from shopping_shorts import headcopy_gen
import uvicorn
from playwright.sync_api import sync_playwright

JOB, PORT = 'hc-wait-qa', 8776
BASE = f'http://127.0.0.1:{PORT}'
SCRIPT = '청소 광인들이 먼지 제거에 목숨 걸게 만든 스펀지. 먼지 뭉침을 싹 없애는 비법이 있다. 소파 틈새 낀 먼지까지 잡는다.'
CANDIDATE = {'label': '궁금증', 'text': '먼지 뭉침을\n싹 없애는 비법', 'subline': '청소가 쉬워지는 이유', 'why': ''}
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

# AI만 가짜(3초 지연) — 나머지는 진짜
calls = []
def fake_suggest(script, family=None, **kw):
    calls.append(time.time()); time.sleep(float(__import__('os').environ.get('HC_DELAY','3'))); return [dict(CANDIDATE)]
headcopy_gen.suggest = fake_suggest
module.headcopy_gen.suggest = fake_suggest

tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
caps = ['청소 광인들이 먼지 제거에 목숨 걸게 만든', '먼지 뭉침을 싹 없애는 비법', '소파 틈새 낀 먼지까지']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH); store.create_mix_job(JOB, [], 3, 'free'); store.update_mix_job(JOB, edit_plan=plan)
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)

ctx_requests = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.on('request', lambda r: ctx_requests.append(r.url) if '/api/produce/scene-style/context/' in r.url else None)
    pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
    need(pg.evaluate("typeof openSceneStyleEditor==='function'&&typeof loadHeadcopySuggest==='function'"), '제작소에 openSceneStyleEditor·loadHeadcopySuggest가 있다')
    pg.evaluate(f"MIX_JOB='{JOB}';PREVIEW_STATUS='ready';STATE.script={SCRIPT!r};STATE.headcopy=null;window._hcCopies=[]")
    # 6단계 진입이 하는 일(자동 후보 생성)을 그대로 걸고, **기다리지 않고** 바로 회색 버튼을 누른다 — 사장님이 한 순서
    # ★evaluate는 promise를 기다린다 — 그대로 부르면 후보가 온 뒤에 버튼을 눌러 검사가 아무것도 안 잰다(1차 실행에서 옛 코드도 통과했다)
    pg.evaluate("(()=>{loadHeadcopySuggest(false);return 1})()")
    pg.evaluate("(()=>{openSceneStyleEditor();return 1})()")
    pg.wait_for_timeout(int(float(__import__('os').environ.get('HC_DELAY','3'))*1000)+4000)
    need(len(ctx_requests) >= 1, f'편집기가 컨텍스트를 요청했다 ({len(ctx_requests)}회)')
    q = urllib.parse.parse_qs(urllib.parse.urlparse(ctx_requests[0]).query) if ctx_requests else {}
    text = (q.get('headcopy_text') or [''])[0]; sub = (q.get('headcopy_subline') or [''])[0]
    need(text == CANDIDATE['text'], f"① 후보보다 먼저 눌러도 컨텍스트 제목 = 후보 1번 (실제: {text!r})")
    need(sub == CANDIDATE['subline'], f"① 보조 제목도 후보의 것 (실제: {sub!r})")
    need(len(calls) == 1, f'② 진입 자동 + 편집기 대기가 겹쳐도 AI 후보 호출 1회 (실제 {len(calls)}회)')
    pg.screenshot(path=str(out / 'editor_after_wait.png'))
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
