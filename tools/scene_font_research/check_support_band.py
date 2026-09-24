"""보조제목(훅 흰 띠)이 화면에 나오나 — 이븐쇼핑 방식(줄여서 물음표)으로 채웠는지까지 잰다 (2026-09-24 사장님 "보조제목이 안 들어감").
  py tools/scene_font_research/check_support_band.py

실물 조사(이븐쇼핑 9편): 대본 첫 문장 = 큰제목 그대로 / 띠 = 그 문장을 줄여 물음표로.
  ① 서버가 만드는 띠 문구가 큰제목과 **다른 글**이다(같으면 화면이 안 그린다 — 2026-09-21 규칙)
  ② 이븐쇼핑 실물과 같은 결과가 나온다
  ③ 진짜 편집기 훅 화면에 띠 글자가 **그려진다**(고치기 전엔 없었다)
"""
import sys, pathlib, threading, functools, http.server, socketserver
ROOT=pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from shopping_shorts.template_copy import scene_text
from playwright.sync_api import sync_playwright
PORT=8796
class Q(socketserver.TCPServer): allow_reuse_address=True
srv=Q(('127.0.0.1',PORT), functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=srv.serve_forever,daemon=True).start()
fails=[]
def need(ok,msg):
    print(('  통과  ' if ok else '★ 실패  ')+msg)
    if not ok: fails.append(msg)
TITLE='건망증 환자를 살려낸 일본 천재의 발명품'
t=scene_text({'text':TITLE})
flat=lambda x:''.join(str(x or '').split())
need(flat(t['bodyTitle'])!=flat(t['hook1']+t['hook2']), f"① 띠가 큰제목과 다른 글 — '{t['bodyTitle']}'")
need(t['bodyTitle']=='건망증 환자를 살려낸 천재의 발명품?', f"② 이븐쇼핑 실물과 같다 — '{t['bodyTitle']}'")
CTX={"jobId":"sb","text":{"channel":"숏템메이커","hook1":t['hook1'],"hook2":t['hook2'],"bodyTitle":t['bodyTitle']},
     "scenes":[{"start":0,"end":2,"caption":"전 세계 건망증 환자들의","caption_visible":True,"beat_idx":0,"kind":"hook"},
               {"start":2,"end":4,"caption":"본문 자막","caption_visible":True,"beat_idx":1,"kind":"body"}]}
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_context(viewport={'width':1500,'height':1000}).new_page()
    pg.goto(f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html?preset=t11',wait_until='domcontentloaded'); pg.wait_for_timeout(4000)
    pg.evaluate('([c])=>window.sceneStyle.load(c,null)',[CTX]); pg.wait_for_timeout(1500)
    pg.evaluate("()=>{window.sceneStyle.show(0);return 1}"); pg.wait_for_timeout(1000)
    drawn=pg.evaluate("""()=>{const L=document.querySelector('#a-live-preview');
      const e=[...L.querySelectorAll('.precision-text')].find(x=>x.dataset.editBind==='bodyTitle');
      return e?{글자:(e.textContent||'').trim(),보임:getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).opacity!=='0'}:null}""")
    need(bool(drawn) and drawn['보임'] and flat(drawn['글자'])==flat(t['bodyTitle']),
         f"③ 훅 화면에 띠 글자가 그려진다 — {drawn} (고치기 전엔 아예 없었다)")
    b.close()
srv.shutdown()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
