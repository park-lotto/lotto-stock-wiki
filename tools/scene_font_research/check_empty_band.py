"""글자 없는 흰 띠를 그리지 않는가 + 완성본 무효 알림 (2026-09-24 고객 제보 2건).
  py tools/scene_font_research/check_empty_band.py

① 임수정님: "자막 들어갈 흰 칸은 있는데 글씨만 없어서 빈 띠로 보여요" → 보조제목이 비면 훅 흰 띠를 안 그린다
② 보조제목이 있으면 띠도 글자도 그대로 나온다(종전 동작 유지)
③ 조율가님: 설정을 바꿔 완성본이 버려지면 서버가 render_invalidated로 알려준다
"""
import sys, time, shutil, threading, pathlib, json, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'w'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from playwright.sync_api import sync_playwright
import http.server, socketserver, functools
PORT = 8803
class Q(socketserver.TCPServer): allow_reuse_address = True
srv = Q(('127.0.0.1', PORT), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
def ctx(body_title):
    return {"jobId": "eb", "text": {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어", "bodyTitle": body_title},
            "scenes": [{"start": 0, "end": 2, "caption": "훅 자막", "caption_visible": True, "beat_idx": 0, "kind": "hook"},
                       {"start": 2, "end": 4, "caption": "본문 자막", "caption_visible": True, "beat_idx": 1, "kind": "body"}]}
# 띠는 별도 '면'으로 그려진다 — 흰색에 가까운 면이 몇 개인지로 센다(셀렉터로 짐작하지 않는다)
BAND = """()=>{const L=document.querySelector('#a-live-preview');const r=L.getBoundingClientRect();
  const white=[...L.querySelectorAll('.precision-patch,.body-material')].filter(e=>{
    const st=getComputedStyle(e);const bg=st.backgroundImage+' '+st.backgroundColor;
    const q=e.getBoundingClientRect();const top=(q.top-r.top)/r.height;
    return /255,\s*255,\s*255|#FFFFFF|rgb\(255, 255, 255\)/i.test(bg)&&top>0.15&&top<0.45&&q.height>4});
  const txt=[...L.querySelectorAll('.precision-text')].find(e=>e.dataset.editBind==='bodyTitle');
  return {흰띠:white.length, 글자:txt?(txt.textContent||'').trim():null}}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1400, 'height': 950}).new_page()
    pg.goto(f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html?preset=t19', wait_until='domcontentloaded'); pg.wait_for_timeout(4000)
    pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [ctx('')]); pg.wait_for_timeout(1200)
    pg.evaluate("()=>{window.sceneStyle.show(0);return 1}"); pg.wait_for_timeout(700)
    empty = pg.evaluate(BAND)
    need(empty['흰띠'] == 0 and not empty['글자'], f"① 보조제목이 비면 흰 띠를 안 그린다 {empty} — 고치기 전엔 빈 띠가 남았다")
    pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [ctx('주부들도 감탄한 천재 아이디어?')]); pg.wait_for_timeout(1200)
    pg.evaluate("()=>{window.sceneStyle.show(0);return 1}"); pg.wait_for_timeout(700)
    filled = pg.evaluate(BAND)
    need(filled['흰띠'] >= 1 and filled['글자'], f"② 보조제목이 있으면 띠와 글자 모두 나온다 {filled}")
    b.close()
srv.shutdown()
# ③ 서버가 완성본 무효를 알려주나
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / 't'
store = Store(module.DB_PATH); store.create_mix_job('inv-qa', [], 2, 'free')
store.update_mix_job('inv-qa', status='done', video_path=str(work / 'final.mp4'))
P2 = 8804
threading.Thread(target=uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=P2, log_level='warning')).run, daemon=True).start()
time.sleep(1.5)
def post(body):
    r = urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{P2}/api/produce/mix/settings',
        data=json.dumps(body).encode('utf-8'), headers={'Content-Type': 'application/json'}))
    return json.loads(r.read())
snap = {"version": 1, "mode": "story", "presetId": "t11", "sceneIndex": 0, "frameKind": "hook"}
d = post({'job_id': 'inv-qa', 'scene_style': snap})
need(d.get('render_invalidated') is True, f"③ 완성본이 있던 job의 설정을 바꾸면 무효를 알려준다 ({d}) — 종전엔 ok만 돌려줘 화면이 조용했다")
d2 = post({'job_id': 'inv-qa', 'scene_style': snap})
need(d2.get('render_invalidated') is False, f"③ 이미 완성본이 없으면 다시 알리지 않는다 ({d2})")
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
