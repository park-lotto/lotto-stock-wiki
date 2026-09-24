"""훅·본문 글꼴 따로 고르기 — 진짜 편집기 페이지로 잰다 (2026-09-24 사장님 "프리셋은 한 개, 훅·본문 스타일 따로").
  py tools/scene_font_research/check_font_per_frame.py <출력폴더는 안 쓴다>

원래 뜻: — 한쪽만 고르면 통일, 다른 쪽에서 고르면 갈라진다. 프리셋 하나가 둘 다 담는다."""
import sys, pathlib, threading, functools, http.server, socketserver, json
ROOT=pathlib.Path(r"C:/Users/TheRose/Desktop/로또의 주식/.tracks/장면폰트")
from playwright.sync_api import sync_playwright
PORT=8781
class Q(socketserver.TCPServer): allow_reuse_address=True
srv=Q(('127.0.0.1',PORT), functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=srv.serve_forever,daemon=True).start()
URL=f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html'
scenes=[{"start":i*2,"end":i*2+2,"caption":f"{i}번 자막","caption_visible":True,"beat_idx":0 if i<4 else i-3,
         "kind":"hook" if i<4 else "body"} for i in range(33)]
CTX={"jobId":"ff","text":{"channel":"숏템메이커","hook1":"이케아도 놀랄","hook2":"한국 천재 발명품","bodyTitle":"이케아도 놀랄 한국 천재 발명품"},"scenes":scenes}
fails=[]
def need(ok,msg):
    print(('  통과  ' if ok else '★ 실패  ')+msg)
    if not ok: fails.append(msg)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_context(viewport={'width':1500,'height':1000}).new_page()
    pg.on('dialog', lambda d: d.accept('프리셋1') if d.type=='prompt' else d.accept())
    pg.goto(URL,wait_until='networkidle'); pg.evaluate('([c])=>window.sceneStyle.load(c,null)',[CTX]); pg.wait_for_timeout(600)
    pg.click('[data-left-tab="scene"]'); pg.click('[data-p20="0"]'); pg.wait_for_timeout(400)
    def fam(i):
        pg.evaluate(f"()=>{{window.sceneStyle.show({i});return 1}}"); pg.wait_for_timeout(200)
        return pg.evaluate("""()=>{const L=document.querySelector('#a-live-preview');
          const e=L.querySelector('.precision-text[data-edit-bind="hook2"],.precision-text[data-edit-bind="bodyTitle"]');
          return e?getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g,''):null}""")
    def pick(scene,idx):
        pg.evaluate(f"()=>{{window.sceneStyle.show({scene});return 1}}"); pg.wait_for_timeout(250)
        pg.click('[data-left-tab="font"]')
        return pg.evaluate(f"()=>{{const c=document.querySelectorAll('[data-font-set]')[{idx}];c.click();return c.dataset.fontSet}}")
    f1=pick(10,3); pg.wait_for_timeout(400)
    h,bd=fam(0),fam(10)
    need(h==bd, f"① 본문에서만 골랐을 때는 훅도 따라온다(통일) — 훅 {h} / 본문 {bd}")
    f2=pick(0,5); pg.wait_for_timeout(400)
    h2,bd2=fam(0),fam(10)
    need(h2!=bd2, f"② 훅에서 따로 고르면 갈라진다 — 훅 {h2} / 본문 {bd2}")
    need(bd2==bd, f"② 본문 글꼴은 그대로 {bd2}")
    pg.click('[data-left-tab="mine"]'); pg.click('[data-my-save]'); pg.wait_for_timeout(500)
    snap=pg.evaluate("()=>JSON.parse(localStorage.getItem('scene_style_my_presets'))[0].snap")
    need(isinstance(snap.get('fontSets'),dict) and len(snap['fontSets'])==2,
         f"③ 프리셋 하나가 훅·본문 둘 다 담는다 — {json.dumps(snap.get('fontSets'),ensure_ascii=False)}")
    # 다시 불러와도 갈라진 채로
    pg.goto(URL,wait_until='networkidle'); pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)',[CTX,snap]); pg.wait_for_timeout(700)
    h3,bd3=fam(0),fam(10)
    need(h3==h2 and bd3==bd2, f"④ 저장본을 다시 열어도 갈라진 채 — 훅 {h3} / 본문 {bd3}")
    # 옛 저장본(fontSet 한 값)은 양쪽 통일
    old={**snap}; old.pop('fontSets'); old['fontSet']=f1
    pg.goto(URL,wait_until='networkidle'); pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)',[CTX,old]); pg.wait_for_timeout(700)
    h4,bd4=fam(0),fam(10)
    need(h4==bd4, f"⑤ 옛 저장본(글꼴 한 값)은 훅·본문 통일 그대로 — {h4}")
    b.close()
srv.shutdown()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
