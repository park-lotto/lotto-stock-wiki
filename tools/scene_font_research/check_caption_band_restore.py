"""이븐쇼핑 본문 흰 띠가 비는 원인 재현 — 브라우저 기억(localStorage)이 자막을 영상 위로 끌어올린다 (2026-09-22).
  py tools/scene_font_research/check_caption_band_restore.py <출력폴더>     (8773 서버 필요)

사장님 제보: 새 영상을 만들었는데 본문 장면의 흰 띠가 비고 자막은 영상 한가운데 떠 있다.
템플릿 정의(precision20-data t11.body)는 자막 줄이 흰 띠(y156~229) 안에 있다. 그런데 편집기는
열릴 때 localStorage 'scene_style_preset'의 captionDrags·captionLayouts·captionPositions를
**작업(job)이 달라도** 그대로 되살린다(precision20-ui.js 1477~1481행).

① 깨끗한 브라우저: t11 본문 장면 → 자막이 흰 띠 안에 있어야 한다
② 같은 브라우저에 옛 작업의 자막 끌기 기록만 남겨 두고 다시 열기 → 자막이 영상 위로 가고 띠가 빈다(재현)
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
URL = 'http://127.0.0.1:8773/out/scene-style-ui-showcase.html?preset=t11'
CTX = {"jobId": "qa", "text": {"channel": "숏템메이커", "hook1": "케이크 위에서", "hook2": "기차가 달리는 정체는", "bodyTitle": "케이크 위에서 기차가 달리는 정체는", "supportTitle": ""},
       "scenes": [{"start": 0, "end": 2, "caption": "이거 실화?", "caption_visible": True, "beat_idx": 0, "kind": "hook"},
                  {"start": 2, "end": 4, "caption": "포클레인에 크레인까지", "caption_visible": True, "beat_idx": 1, "kind": "body"}]}
MEASURE = """()=>{
  const layer=document.querySelector('#a-live-preview');
  const cap=layer.querySelector('.precision-text[data-edit-bind="caption"]');
  const media=layer.querySelector('video,img.media,.media');
  const L=layer.getBoundingClientRect(), c=cap?cap.getBoundingClientRect():null;
  // 흰 띠 = 자막 줄 밑에 깔린 밝은 면(surface). 밝기 240 이상인 면 중 자막 y 근처
  const surfaces=[...layer.querySelectorAll('.precision-surface, .body-material, [data-surface]')].map(s=>{const r=s.getBoundingClientRect();const bg=getComputedStyle(s).backgroundImage+getComputedStyle(s).backgroundColor;return {top:(r.top-L.top)/L.height*100,h:r.height/L.height*100,bg};});
  return {capTop:c?(c.top-L.top)/L.height*100:null, capH:c?c.height/L.height*100:null, capColor:c?getComputedStyle(cap).color:null,
          surfaces, layerH:L.height};
}"""
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = ctx.new_page()
    pg.goto(URL, wait_until='networkidle'); pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [CTX]); pg.evaluate('()=>window.sceneStyle.show(1)'); pg.wait_for_timeout(600)
    m1 = pg.evaluate(MEASURE); pg.screenshot(path=str(out / 'A_clean_body.png'))
    white = [s for s in m1['surfaces'] if 'rgb(255, 255, 255)' in s['bg'] or '#FFFFFF' in s['bg'] or 'rgb(250, 251, 250)' in s['bg']]
    band = white[0] if white else None
    # 흰 띠(surface)는 자막이 '제목 아래' 자리일 때 높이 0으로 접히고 자막 자신의 흰 바탕이 띠가 된다 → 자막 top이 띠 시작(≈21.1)과 같으면 띠 안
    inband = band and m1['capTop'] is not None and abs(m1['capTop'] - band['top']) < 1
    need(bool(inband), f"① 깨끗한 브라우저: 본문 자막이 흰 띠 자리(top {m1['capTop']:.1f} ≈ 띠 {band and round(band['top'],1)})")
    # 옛 작업에서 자막을 영상 위로 끌어 놓은 기록만 남긴다(작업 번호는 키에 없다 — 어느 작업이든 되살아난다)
    pg.evaluate("""()=>localStorage.setItem('scene_style_preset', JSON.stringify({presetId:'t11', captionDrags:{'t11:story:1:caption':{x:50,y:62}}, captionLayouts:{'t11:story:1:caption':{placement:'free',w:100,h:10,background:'#FFFFFF',color:'#111111'}}}))""")
    pg.goto(URL, wait_until='networkidle'); pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [CTX]); pg.evaluate('()=>window.sceneStyle.show(1)'); pg.wait_for_timeout(600)
    m2 = pg.evaluate(MEASURE); pg.screenshot(path=str(out / 'B_after_restore_body.png'))
    stayed = m2['capTop'] is not None and abs(m2['capTop'] - m1['capTop']) < 1
    need(bool(stayed), f"② 옛 작업의 자막 끌기 기록이 브라우저에 남아 있어도 새 작업 자막은 띠 안 그대로 (자막 top {m2['capTop']} vs 깨끗 {m1['capTop']}) — 고치기 전엔 82.9로 영상 위로 갔다")
    json.dump({'clean': m1, 'restored': m2}, open(out / 'measure.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
