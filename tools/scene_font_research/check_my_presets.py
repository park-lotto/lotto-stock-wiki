"""내 프리셋 탭(맨 앞) + 마지막 저장·적용 프리셋으로 첫 시작 — 진짜 편집기 페이지(8773 정적 서버)로 잰다 (2026-09-23 사장님).
  py tools/scene_font_research/check_my_presets.py <출력폴더>
  ① 탭 순서 맨 앞이 '내 프리셋', 처음엔 빈 안내
  ② t05+폰트세트 고른 뒤 저장 → 카드 1장 / 새로고침 뒤에도 카드 남고, 첫 시작 템플릿이 t05·그 폰트세트(마지막 저장 기억)
  ③ 다른 템플릿(t11)으로 바꾼 뒤 '적용' → t05·폰트세트로 돌아오고, 새로고침해도 t05로 시작
  ④ 삭제 → 카드 0
"""
import sys, pathlib, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
PORT = 8773
class Q(socketserver.TCPServer): allow_reuse_address = True
srv = Q(('127.0.0.1', PORT), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
STATE = "()=>{const s=window.sceneStyle.snapshot();return {preset:s&&s.presetId,fontSet:s&&s.fontSet,cards:document.querySelectorAll('[data-my-id]').length,tabs:[...document.querySelectorAll('[data-left-tab]')].map(b=>b.dataset.leftTab)}}"
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = ctx.new_page()
    pg.on('dialog', lambda d: d.accept('내 첫 프리셋') if d.type == 'prompt' else d.accept())
    pg.goto(URL, wait_until='networkidle'); pg.click('[data-left-tab="mine"]'); pg.wait_for_timeout(300); s = pg.evaluate(STATE)
    need(s['tabs'][0] == 'mine' and len(s['tabs']) == 6, f"① 탭 맨 앞이 내 프리셋 ({s['tabs']})")
    need(s['cards'] == 0 and pg.evaluate("!!document.querySelector('.my-preset-pane .font-template-empty')") and not pg.evaluate("document.querySelector('.my-preset-pane').hidden"), '① 처음엔 빈 안내가 보인다')
    pg.click('[data-left-tab="scene"]'); pg.click('[data-p20="4"]'); pg.click('[data-left-tab="font"]'); fs = pg.evaluate("()=>{const c=document.querySelectorAll('[data-font-set]')[2];c.click();return c.dataset.fontSet}")
    pg.click('[data-left-tab="mine"]'); pg.click('[data-my-save]'); pg.wait_for_timeout(300); s = pg.evaluate(STATE)
    need(s['cards'] == 1 and s['fontSet'] == fs, f"② 저장 → 카드 1장 (preset {s['preset']}, 폰트세트 {s['fontSet']})"); saved_preset = s['preset']
    pg.goto(URL, wait_until='networkidle'); pg.click('[data-left-tab="mine"]'); pg.wait_for_timeout(300); s2 = pg.evaluate(STATE)
    need(s2['cards'] == 1 and s2['preset'] == saved_preset and s2['fontSet'] == fs, f"② 새로고침 → 카드 남고 마지막 저장 템플릿으로 시작 ({s2['preset']}, {s2['fontSet']}) — 고치기 전엔 탭 자체가 없다")
    pg.screenshot(path=str(out / 'my_presets.png'))
    pg.click('[data-left-tab="scene"]'); pg.click('[data-p20="0"]'); pg.click('[data-left-tab="font"]'); pg.click('[data-font-set=""]'); s3 = pg.evaluate(STATE)
    need(s3['preset'] != saved_preset and s3['fontSet'] == '', f"③ 다른 템플릿으로 바꿈 ({s3['preset']})")
    pg.click('[data-left-tab="mine"]'); pg.click('[data-my-apply]'); pg.wait_for_timeout(400); s4 = pg.evaluate(STATE)
    need(s4['preset'] == saved_preset and s4['fontSet'] == fs, f"③ 적용 → 저장한 템플릿·폰트세트로 돌아온다 ({s4['preset']}, {s4['fontSet']})")
    pg.goto(URL, wait_until='networkidle'); s5 = pg.evaluate(STATE)
    need(s5['preset'] == saved_preset and s5['fontSet'] == fs, f"③ 새로고침해도 적용한 프리셋으로 시작 ({s5['preset']}, {s5['fontSet']})")
    pg.click('[data-left-tab="mine"]'); pg.click('[data-my-del]'); pg.wait_for_timeout(300); s6 = pg.evaluate(STATE)
    need(s6['cards'] == 0, f"④ 삭제 → 카드 {s6['cards']}")
    # ⑤ 2026-09-23 고객(홍광수) 제보: "33장면 중 5번에서 저장했더니 적용을 누르면 계속 5번 장면부터 나옵니다."
    #    프리셋은 **취향만** 옮겨야 한다 — 보던 장면·그때의 문구·장면별 자막 손질은 안 옮긴다.
    ctx = {"jobId": "mine33", "text": {"channel": "숏템메이커", "hook1": "이케아도 놀랄", "hook2": "한국 천재 발명품",
           "bodyTitle": "이케아도 놀랄 한국 천재 발명품"},
           "scenes": [{"start": i*2, "end": i*2+2, "caption": f"{i}번 자막", "caption_visible": True,
                       "beat_idx": i, "kind": "hook" if i == 0 else "body"} for i in range(33)]}
    pg.goto(URL, wait_until='networkidle')
    pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [ctx]); pg.wait_for_timeout(500)
    pg.click('[data-left-tab="scene"]'); pg.click('[data-p20="0"]'); pg.wait_for_timeout(300)
    pg.evaluate("()=>{window.sceneStyle.show(5);return 1}"); pg.wait_for_timeout(300)
    pg.click('[data-left-tab="font"]'); pg.evaluate("()=>{document.querySelectorAll('[data-font-set]')[2].click();return 1}")
    pg.click('[data-left-tab="mine"]'); pg.click('[data-my-save]'); pg.wait_for_timeout(500)
    snap = pg.evaluate("()=>JSON.parse(localStorage.getItem('scene_style_my_presets'))[0].snap")
    need(snap.get('sceneIndex') is None and snap.get('text') is None,
         f"⑤ 프리셋에 장면번호·문구를 담지 않는다 (sceneIndex {snap.get('sceneIndex')}, text {'있음' if snap.get('text') else '없음'}) — 고치기 전엔 sceneIndex=5·그 작업 제목이 들어갔다")
    pg.evaluate("()=>{window.sceneStyle.show(20);return 1}"); pg.wait_for_timeout(200)
    pg.click('[data-left-tab="mine"]'); pg.click('[data-my-apply]'); pg.wait_for_timeout(700)
    now = pg.evaluate("()=>window.sceneStyle.snapshot().sceneIndex")
    need(now == 20, f"⑤ 적용해도 보던 장면(20번)에 머문다 (실제 {now}) — 고치기 전엔 저장할 때의 5번으로 튀었다")
    title = pg.evaluate("()=>window.sceneStyle.context().text.hook1")
    need(title == '이케아도 놀랄', f"⑤ 적용이 이 작업 제목을 안 건드린다 ('{title}')")
    b.close()
srv.shutdown()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
