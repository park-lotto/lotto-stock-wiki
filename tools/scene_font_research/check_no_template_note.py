"""'원본 영상 그대로'를 고르면 오른쪽이 텅 비던 것 — 안내가 뜨나 (2026-09-24 사장님 제보).
  py tools/scene_font_research/check_no_template_note.py
  ① 템플릿을 고른 상태: 문구 칸이 보이고 안내는 숨음
  ② '원본 영상 그대로': 문구 칸 0개 + 안내가 보인다(고치기 전엔 아무것도 없었다)
  ③ 안내의 '템플릿 고르러 가기'를 누르면 장면 탭이 열린다
  ④ 다시 템플릿을 고르면 안내는 사라지고 문구 칸이 돌아온다
"""
import sys, pathlib, threading, functools, http.server, socketserver
ROOT=pathlib.Path(__file__).resolve().parents[2]
from playwright.sync_api import sync_playwright
PORT=8795
class Q(socketserver.TCPServer): allow_reuse_address=True
srv=Q(('127.0.0.1',PORT), functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=srv.serve_forever,daemon=True).start()
URL=f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html'
fails=[]
def need(ok,msg):
    print(('  통과  ' if ok else '★ 실패  ')+msg)
    if not ok: fails.append(msg)
PROBE="""()=>{const vis=e=>!!(e&&e.offsetParent!==null);
  const n=document.querySelector('.no-template-note');
  return {안내보임:vis(n),
          문구칸:[...document.querySelectorAll('.scene-text-panel > .text-group')].filter(vis).length,
          장면탭활성:!!document.querySelector('[data-left-tab="scene"].active')}}"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_context(viewport={'width':1500,'height':1000}).new_page()
    pg.goto(URL,wait_until='networkidle'); pg.wait_for_timeout(800)
    a=pg.evaluate(PROBE); need(a['문구칸']>0 and not a['안내보임'], f"① 템플릿 고른 상태: 문구칸 {a['문구칸']}개·안내 숨음")
    pg.click('[data-none]'); pg.wait_for_timeout(700)
    c=pg.evaluate(PROBE); need(c['문구칸']==0 and c['안내보임'], f"② 원본 그대로: 문구칸 0 + 안내 보임 (실제 {c}) — 고치기 전엔 안내 없이 텅 비었다")
    pg.click('[data-left-tab="font"]'); pg.wait_for_timeout(300)
    pg.click('[data-goto-template]'); pg.wait_for_timeout(500)
    d=pg.evaluate(PROBE); need(d['장면탭활성'], f"③ '템플릿 고르러 가기' → 장면 탭 열림 (실제 {d['장면탭활성']})")
    pg.click('[data-p20="0"]'); pg.wait_for_timeout(700)
    e=pg.evaluate(PROBE); need(e['문구칸']>0 and not e['안내보임'], f"④ 템플릿 다시 고르면 안내 사라지고 문구칸 {e['문구칸']}개")
    pg.screenshot(path=str(pathlib.Path(sys.argv[1]).resolve()/'note.png')) if len(sys.argv)>1 else None
    b.close()
srv.shutdown()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
