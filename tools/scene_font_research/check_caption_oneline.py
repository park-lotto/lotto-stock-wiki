"""자막 한 줄 맞춤 + 자막박스 모양 '이 장면만' — 실제 편집기에서 잰다 (2026-09-22 사장님 2건).
  py tools/scene_font_research/check_caption_oneline.py <출력폴더>     (8773 서버 필요, 트랙 폴더에서 띄운 것)

① 이븐쇼핑 본문 흰 띠(한 줄 규격)에 긴 자막을 130%로 키우면 → 두 줄로 꺾이지 않고 글자를 줄여 한 줄에 들어간다
   (고치기 전: 3줄까지 허용해 "스트레스를 요철 / 구조 스펀지가"처럼 두 줄로 꺾였다)
② 자막박스 모양을 [이 장면만]으로 고르면 다른 장면의 모양은 그대로 / [모든 장면]이면 다 바뀐다
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
URL = 'http://127.0.0.1:8773/out/scene-style-ui-showcase.html?preset=t11'
LONG = '스트레스를 요철 구조 스펀지가 다 풀어준다'
CTX = {"jobId": "qa", "text": {"channel": "숏템메이커", "hook1": "빨래 먼지까지", "hook2": "잡아낸 정체는", "bodyTitle": "빨래 먼지까지 잡아낸 정체는", "supportTitle": ""},
       "scenes": [{"start": 0, "end": 2, "caption": "이거 실화?", "caption_visible": True, "beat_idx": 0, "kind": "hook"},
                  {"start": 2, "end": 4, "caption": LONG, "caption_visible": True, "beat_idx": 1, "kind": "body"},
                  {"start": 4, "end": 6, "caption": "진절머리가 났던 상황을", "caption_visible": True, "beat_idx": 2, "kind": "body"}]}
CAP = """()=>{const c=document.querySelector('#a-live-preview .precision-text[data-edit-bind="caption"]');if(!c)return null;
  const r=document.createRange();r.selectNodeContents(c);const rects=[...r.getClientRects()];
  const lines=new Set(rects.map(x=>Math.round(x.top))).size;
  return {lines,font:parseFloat(getComputedStyle(c).fontSize),fit:c.dataset.oneLineFit||null,text:c.textContent.trim().slice(0,20)};}"""
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.goto(URL, wait_until='networkidle'); pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [CTX]); pg.evaluate('()=>window.sceneStyle.show(1)'); pg.wait_for_timeout(500)
    base = pg.evaluate(CAP)
    need(base and base['lines'] == 1, f"① 100%: 긴 자막이 한 줄 ({base})")
    # 자막 크기 130% — 자막 칸의 [+] 스텝퍼를 누른다(10%씩 3번)
    # 자막 칸(captionField)의 글자 스텝퍼 [＋](data-font-step=0.1)
    plus = pg.query_selector('#captionField [data-font-step="0.1"], [data-field-key="caption"] [data-font-step="0.1"], .caption-field [data-font-step="0.1"]')
    if not plus:
        plus = next((h for h in pg.query_selector_all('[data-font-step="0.1"]') if h.evaluate("e=>!!e.closest('.font-stepper')&&!e.closest('.font-stepper').hidden&&/caption|자막/.test((e.closest('label,div,section')||{}).textContent||'')")), None)
    need(plus is not None, '① 자막 크기 [+] 버튼을 찾았다')
    if plus:
        for _ in range(3): plus.evaluate('e=>e.click()'); pg.wait_for_timeout(120)   # 스텝퍼는 칸을 누르기 전엔 숨겨져 있어 JS로 누른다
        pg.wait_for_timeout(400)
        big = pg.evaluate(CAP); pg.screenshot(path=str(out / 'caption_130.png'), clip={'x': 585, 'y': 255, 'width': 320, 'height': 575})
        need(big and big['lines'] == 1, f"① 130%: 두 줄로 꺾이지 않고 한 줄 (lines {big and big['lines']}, font {big and big['font']}, fit {big and big['fit']}) — 고치기 전엔 2줄")
        need(big and base and big['font'] < base['font'] * 1.3 + 0.5, f"① 130%인데 글자는 꺾이기 직전 크기로 줄었다 (100% {base and base['font']} → {big and big['font']})")
    # ② 모양 범위
    snap = lambda: pg.evaluate('()=>window.sceneStyle.snapshot().captionLayouts||{}')
    pg.evaluate('()=>window.sceneStyle.show(1)'); pg.wait_for_timeout(200)
    pg.evaluate("()=>{document.querySelector('.caption-looks')?.closest('details')?.setAttribute('open','');}")
    click = lambda sel: pg.evaluate(f"document.querySelector('{sel}').click()")   # 접힌 패널 안이라 JS로 누른다
    click('[data-caption-look-scope="one"]'); click('[data-caption-look="0"]'); pg.wait_for_timeout(300)
    s1 = snap(); k1, k2 = 't11:story:1:caption', 't11:story:2:caption'
    need(s1.get(k1, {}).get('look') == 0 and 'look' not in s1.get(k2, {}), f"② [이 장면만]: 2장면만 모양 0, 3장면은 그대로 (2장면 {s1.get(k1)} / 3장면 {s1.get(k2)})")
    click('[data-caption-look-scope="all"]'); click('[data-caption-look="3"]'); pg.wait_for_timeout(300)
    s2 = snap()
    need(s2.get(k1, {}).get('look') == 3 and s2.get(k2, {}).get('look') == 3, f"② [모든 장면]: 2·3장면 모두 모양 3 ({s2.get(k1)} / {s2.get(k2)})")
    pg.screenshot(path=str(out / 'look_scope.png'))
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
