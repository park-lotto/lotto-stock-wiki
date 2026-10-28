"""새 편집기 잠금 — 고객은 못 쓰고 관리자·스위치만 (2026-09-23 사장님 "모든 고객이 못 쓰게 막으라니까, 라이브하고 나서 켠다").
  py tools/scene_font_research/check_new_editor_gate.py <출력폴더>

진짜 앱(격리 DB). 고객은 _cid/_is_admin을 고객 계정으로 바꿔 흉내낸다.
  ① 고객·스위치 꺼짐: flags.allowed=false, 컨텍스트 API 403, 6단계 회색 버튼 숨김, openSceneStyleEditor()가 아무것도 안 연다
  ② 관리자·스위치 꺼짐: allowed=true, 버튼 보임, 팝업 열림
  ③ 고객·스위치 "1": allowed=true, 컨텍스트 200
"""
import sys, time, shutil, threading, pathlib, json, urllib.request, urllib.error
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright

JOB, PORT = 'gate-qa', 8780
BASE = f'http://127.0.0.1:{PORT}'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(['첫 문장', '둘째 문장'])]}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH)
CUST = store.create_customer('gate-cust', 'pw1234', email='gate@qa.test')  # 승인된 진짜 고객(가짜 id면 미리보기 페이지로 빠진다)
store.create_mix_job(JOB, [], 2, 'free', customer_id=CUST); store.update_mix_job(JOB, edit_plan=plan)
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)

_orig_cid, _orig_admin = module._cid, module._is_admin
def as_customer(): module._cid = lambda request: CUST; module._is_admin = lambda cid: False
def as_admin(): module._cid, module._is_admin = _orig_cid, _orig_admin
def get(path):
    try:
        r = urllib.request.urlopen(f'{BASE}{path}'); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
PROBE = """()=>{const btn=document.querySelector('.panel[data-step="3"] button.btn[onclick="openSceneStyleEditor()"]');return {btnVisible:!!(btn&&btn.offsetParent!==null&&!btn.hidden),dialog:!!document.querySelector('dialog[open]')}}"""
def page_probe(b):
    pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page(); pg.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2500); pg.wait_for_function('typeof showPanel==="function"', timeout=15000)
    pg.evaluate(f"MIX_JOB='{JOB}';PREVIEW_STATUS='ready';_stepReady=true;cur=3;showPanel()"); pg.wait_for_timeout(800)
    before = pg.evaluate(PROBE); pg.evaluate("(()=>{openSceneStyleEditor();return 1})()"); pg.wait_for_timeout(2500); after = pg.evaluate(PROBE); pg.close(); return before, after

with sync_playwright() as p:
    b = p.chromium.launch()
    # ① 고객, 스위치 꺼짐
    as_customer()
    st, d = get('/api/produce/scene-style/flags'); need(st == 200 and d.get('allowed') is False, f'① 고객·스위치 꺼짐: flags.allowed=false ({d})')
    st2, _ = get(f'/api/produce/scene-style/context/{JOB}'); need(st2 == 403, f'① 고객: 컨텍스트 API 403 (실제 {st2})')
    before, after = page_probe(b); need(not before['btnVisible'] and not after['dialog'], f'① 고객: 회색 버튼 숨김·열어도 팝업 없음 ({before} → {after}) — 고치기 전엔 버튼 보이고 팝업 열림')
    # ② 관리자, 스위치 꺼짐
    as_admin()
    st, d = get('/api/produce/scene-style/flags'); need(st == 200 and d.get('allowed') is True, f'② 관리자: flags.allowed=true ({d})')
    before, after = page_probe(b); need(before['btnVisible'] and after['dialog'], f'② 관리자: 버튼 보이고 팝업 열림 ({before} → {after})')
    # ③ 고객, 스위치 "1"
    Store(module.DB_PATH).set_setting('scene_style_inline_enabled', '1'); as_customer()
    st, d = get('/api/produce/scene-style/flags'); st2, _ = get(f'/api/produce/scene-style/context/{JOB}')
    need(d.get('allowed') is True and st2 == 200, f'③ 고객·스위치 "1": allowed=true, 컨텍스트 200 (실제 {d}, {st2})')
    as_admin(); b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
