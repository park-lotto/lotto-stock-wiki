# -*- coding: utf-8 -*-
"""원본(plain) 자막 자리 버그 — 2026-09-25 Opus 검토에서 나온 것들을 실제 편집기에서 누른다.
  py tools/scene_font_research/check_plain_caption_bugs.py <출력폴더>      (8773 서버 필요)
 ① 원본에서 '모든 장면'으로 박스 높이를 바꿔도 다른 장면 자막이 맨 위로 튀지 않는다(썰쇼핑형·고정형)
    — 고치기 전: 썰쇼핑형 22→0.2%, 고정형 22→26.1% (spreadCaption이 원본 예외 없이 'title' 배치를 박았다)
 ② 원본에서 '위치 초기화'를 누르면 제 자리(22%) — 고치기 전: 맨 위
 ③ 원본에서 모양을 고른 프리셋을 적용해도 자막이 맨 위로 안 간다(applyCaptionLook도 같은 결함)
 ④ 훅 장면을 보며 저장한 프리셋도 본문에서 옮긴 자막 자리를 담는다(썰쇼핑형 템플릿)
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
CAP = "#a-live-preview .precision-text[data-edit-bind=caption]"
def page(b):
    pg = b.new_page(viewport={'width': 1600, 'height': 1600}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept('P') if d.type == 'prompt' else d.accept())
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    pg.evaluate("()=>{try{localStorage.removeItem('scene_style_my_presets')}catch(e){}return 1}")
    return pg, errs
def helpers(pg):
    show = lambda i: (pg.evaluate(f'window.sceneStyle.show({i})'), pg.wait_for_timeout(300))
    top = lambda: pg.evaluate(f"(()=>{{const e=document.querySelector('{CAP}');const r=document.querySelector('#a-live-preview').getBoundingClientRect();return e?Math.round((e.getBoundingClientRect().top-r.top)/r.height*1000)/10:null}})()")
    def open_panel(): pg.evaluate("()=>{const s=document.querySelector('[data-caption-look-scope]');for(let e=s;e;e=e.parentElement){if(e.tagName==='DETAILS')e.open=true;if(e.hidden)e.hidden=false}return 1}")
    def put(k, v): open_panel(); pg.evaluate("([k,v])=>{const i=document.querySelector(`[data-caption-layout=\"${k}\"]`);i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));return 1}", [k, v]); pg.wait_for_timeout(250)
    return show, top, open_panel, put
with sync_playwright() as p:
    b = p.chromium.launch(); allerr = []
    for mode in ('story', 'continuous'):
        pg, errs = page(b); allerr += errs; show, top, open_panel, put = helpers(pg)
        if mode == 'continuous': pg.evaluate("()=>{document.querySelector('[data-template-mode=\"continuous\"]').click();return 1}"); pg.wait_for_timeout(1000)
        pg.click('[data-none]'); pg.wait_for_timeout(800)
        show(5); base = top(); show(3); put('h', '12'); show(5); a1 = top()
        need(abs(a1 - base) <= 0.6, f'① [{mode}] 3번에서 높이를 바꿔도 5번 자막 자리 그대로 {base} → {a1}')
        show(5); pg.click('[data-caption-placement="title"]'); pg.wait_for_timeout(300); r = top()
        need(abs(r - base) <= 0.6, f'② [{mode}] 위치 초기화 → 제 자리 {r} (기본 {base})')
        open_panel(); pg.click('[data-caption-look="2"]'); pg.wait_for_timeout(300)
        pg.click('[data-left-tab="mine"]'); pg.click('[data-my-save]'); pg.wait_for_timeout(300)
        pg.click('[data-my-id] [data-my-apply]'); pg.wait_for_timeout(600); pg.click('[data-left-tab="scene"]')
        got = []
        for i in (2, 5, 8): show(i); got.append(top())
        need(all(abs(v - base) <= 0.6 for v in got), f'③ [{mode}] 모양 담은 프리셋 적용 뒤에도 자막 제 자리 {got} (기본 {base})')
        pg.close()
    # ④ 썰쇼핑형 템플릿: 본문에서 자막을 옮기고 훅 장면을 보며 저장
    pg, errs = page(b); allerr += errs; show, top, open_panel, put = helpers(pg)
    show(2); box = pg.locator(CAP).bounding_box(); x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x, y - 150, steps=8); pg.mouse.up(); pg.wait_for_timeout(300)
    show(0); pg.click('[data-left-tab="mine"]'); pg.click('[data-my-save]'); pg.wait_for_timeout(300)
    pos = pg.evaluate("()=>JSON.parse(localStorage.getItem('scene_style_my_presets'))[0].snap.positions")
    need(bool(pos and pos['caption'] and pos['caption']['drag']), f'④ 훅 장면에서 저장해도 옮긴 자막 자리를 담는다 {pos and pos["caption"]}')
    pg.close()
    need(not allerr, f'페이지 오류 {allerr[:3]}'); b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건'); sys.exit(1 if fails else 0)
