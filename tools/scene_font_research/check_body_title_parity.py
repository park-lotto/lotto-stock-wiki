"""본문 제목 크기: 편집기(작은 미리보기)와 렌더러(1080×1920)가 같은 비율인가 (2026-09-22 사장님 "왜 폰트 크기가 다르냐").
  py tools/scene_font_research/check_body_title_parity.py <출력폴더>     (8773 서버 필요)
실측 job d29a2bd26032(본문 제목 170%): 편집기 9.16% / 렌더러 10.77%(화면 폭 대비) — 칸 높이 맞춤 반복문이 0.5px×80번(40px 상한)이라
렌더러에서 덜 줄었다. 고친 뒤엔 두 화면의 비율 차이가 3% 안이어야 한다.
"""
import sys, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
URL = 'http://127.0.0.1:8773/out/scene-style-ui-showcase.html'
CTX = {"jobId": "qa", "text": {"channel": "숏템메이커", "hook1": "빗질 한 번에 무슨", "hook2": "일이 벌어질까", "bodyTitle": "빗질 한 번에 무슨 일이 벌어질까", "supportTitle": ""},
       "scenes": [{"start": 0, "end": 2, "caption": "이거 실화?", "caption_visible": True, "beat_idx": 0, "kind": "hook"},
                  {"start": 2, "end": 4, "caption": "아침마다 머리 감고", "caption_visible": True, "beat_idx": 1, "kind": "body"}]}
SNAP = {"version": 1, "mode": "story", "presetId": "t11", "sceneIndex": 1, "frameKind": "body", "fontScales": {"t11:body:bodyTitle": 1.7}}
STYLE = "body *{visibility:hidden!important}#a-live-preview,#a-live-preview *{visibility:visible!important}#a-live-preview{position:fixed!important;left:0!important;top:0!important;width:1080px!important;height:1920px!important;max-width:none!important;max-height:none!important;border:0!important;border-radius:0!important;box-shadow:none!important;background:transparent!important;z-index:99999!important}.precision-base,.precision-media,.scene-media-clip,.precision-badge{display:none!important}html,body{background:transparent!important}"
M = """()=>{const P=document.querySelector('#a-live-preview');const e=P.querySelector('.precision-text[data-edit-bind="bodyTitle"]');const cs=getComputedStyle(e);return {pct:parseFloat(cs.fontSize)/P.clientWidth*100,over:e.scrollHeight>e.clientHeight+1,font:parseFloat(cs.fontSize)}}"""
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page(); pg.goto(URL, wait_until='networkidle')
    pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)', [CTX, SNAP]); pg.evaluate('()=>window.sceneStyle.show(1)'); pg.wait_for_timeout(500); ed = pg.evaluate(M)
    pg2 = b.new_context(viewport={'width': 1920, 'height': 2200}).new_page(); pg2.goto(URL + '?qa=1', wait_until='networkidle'); pg2.add_style_tag(content=STYLE)
    pg2.evaluate('([c,s])=>window.sceneStyle.load(c,s)', [CTX, SNAP]); pg2.evaluate('async()=>{await document.fonts.ready;window.sceneStyle.refresh();window.sceneStyleExporting=true}'); pg2.evaluate('()=>window.sceneStyle.show(1)'); pg2.wait_for_timeout(500); rd = pg2.evaluate(M)
    pg2.screenshot(path=str(out / 'renderer_body.png'), clip={'x': 0, 'y': 0, 'width': 1080, 'height': 800}); b.close()
print(f'  편집기 {ed["pct"]:.2f}% ({ed["font"]:.1f}px) / 렌더러 {rd["pct"]:.2f}% ({rd["font"]:.1f}px)')
need(abs(ed['pct'] - rd['pct']) / max(ed['pct'], 1e-6) < 0.03, f"본문 제목(170%) 크기 비율이 편집기·렌더러 3% 안 (차이 {abs(ed['pct']-rd['pct'])/ed['pct']*100:.1f}%) — 고치기 전엔 17.6%")
need(not rd['over'], '렌더러에서 본문 제목이 칸을 넘치지 않는다 — 고치기 전엔 넘침')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
