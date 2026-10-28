# -*- coding: utf-8 -*-
"""자막박스: '모양'은 모든 장면 공통, '위치 이동'만 장면별 (2026-09-22 사장님).  실제 편집기에서 눌러서 확인한다.
  py tools/scene_font_research/check_caption_scope.py <출력폴더>      (8773 서버 필요)
고치기 전 코드에서는 ①이 실패한다(모양이 누른 장면 키 하나에만 저장됐다 — 실측 {'t11:story:1:caption': 2}).
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
CAP = "#a-live-preview .precision-text[data-edit-bind=caption]"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 1600}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    # 샘플 작업대에는 실제 job 컨텍스트가 없다(context()=null) → 화면의 '1 / 12' 표시에서 장면 수를 읽는다
    total = pg.evaluate("(()=>{for(const e of document.querySelectorAll('body *')){const m=e.childElementCount===0&&e.textContent.trim().match(/^\d+\s*\/\s*(\d+)$/);if(m)return +m[1]}return 0})()"); print('장면 수', total)
    assert total > 3, '장면 수를 못 읽었다'
    show = lambda i: (pg.evaluate(f'window.sceneStyle.show({i})'), pg.wait_for_timeout(250))
    def pick(look):   # 고객처럼: 모양 버튼이 든 접힌 카드들을 펼친 뒤 진짜 클릭
        sel = f'[data-caption-look="{look}"]'
        pg.evaluate("sel=>{for(let e=document.querySelector(sel);e;e=e.parentElement){if(e.tagName==='DETAILS')e.open=true;if(e.hidden)e.hidden=false}}", sel)
        pg.wait_for_timeout(200); pg.locator(sel).scroll_into_view_if_needed(); pg.click(sel); pg.wait_for_timeout(400)
    look_of = lambda: {int(k.split(':')[2]): v.get('look') for k, v in pg.evaluate('window.sceneStyle.snapshot()')['captionLayouts'].items()}
    paint = lambda: pg.evaluate(f"(()=>{{const e=document.querySelector('{CAP}');return e?getComputedStyle(e).color:null}})()")
    top = lambda: pg.evaluate(f"(()=>{{const e=document.querySelector('{CAP}');return e?Math.round(e.getBoundingClientRect().top):null}})()")
    show(1); base_paint = paint(); tops0 = {}
    for i in range(1, total): show(i); tops0[i] = top()
    # ① 2번째 장면에서 모양을 바꾸면 전 장면이 바뀐다
    show(1); pick('2'); looks = look_of()
    need(all(looks.get(i) == 2 for i in range(total)), f'① 모양(흰 바탕 번짐)을 한 장면에서 고르면 저장값이 전 장면에 들어간다 {looks}')
    seen = []
    for i in (1, 2, total - 1): show(i); seen.append(paint())
    need(len(set(seen)) == 1 and seen[0] != base_paint, f'① 화면에서도 2·3·마지막 장면 자막 모양이 같이 바뀐다 {seen}')
    # ② 3번째 장면에서 자막을 끌어 옮기면 그 장면만 움직인다
    show(2); box = pg.locator(CAP).bounding_box(); pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2); pg.mouse.down()
    pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2 - 120, steps=8); pg.mouse.up(); pg.wait_for_timeout(400)
    moved = top(); drags = pg.evaluate('window.sceneStyle.snapshot()')['captionDrags']; print('  끌어 옮긴 뒤 captionDrags 키', list(drags))
    need(moved is not None and abs(moved - tops0[2]) > 30, f'② 3번째 장면 자막이 실제로 움직였다 {tops0[2]} → {moved}')
    others = {}
    for i in (1, 3): show(i); others[i] = top()
    need(all(abs(others[i] - tops0[i]) <= 1 for i in others), f'② 2·4번째 장면 자막 위치는 그대로 {others} (원래 { {i: tops0[i] for i in others} })')
    # ③ 다른 장면에서 모양을 또 바꿔도 3번째 장면의 위치는 남는다
    show(4); pick('5'); looks = look_of()
    need(all(looks.get(i) == 5 for i in range(total)), f'③ 다른 장면에서 모양(짙은 띠)을 바꿔도 전 장면 적용 {sorted(set(looks.values()))}')
    show(2); need(abs(top() - moved) <= 1, f'③ 모양을 바꿔도 3번째 장면의 옮긴 위치는 유지 {moved} → {top()}')
    pg.locator('#a-live-preview').screenshot(path=str(out / 'caption_scene3.png'))
    # ④ 저장값을 새 페이지에서 불러와도 같다
    snap = pg.evaluate('window.sceneStyle.snapshot()')
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from shopping_shorts import scene_style
    v = scene_style.validate_snapshot(json.loads(json.dumps(snap)))
    pg2 = b.new_page(viewport={'width': 1600, 'height': 1600}); pg2.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    pg2.evaluate('s=>window.sceneStyle.load(window.sceneStyle.context(),s)', v); pg2.evaluate('window.sceneStyle.show(2)'); pg2.wait_for_timeout(500)
    t2 = pg2.evaluate(f"Math.round(document.querySelector('{CAP}').getBoundingClientRect().top)")
    l2 = {int(k.split(':')[2]): x.get('look') for k, x in pg2.evaluate('window.sceneStyle.snapshot()')['captionLayouts'].items()}
    need(abs(t2 - moved) <= 1 and all(l2.get(i) == 5 for i in range(total)), f'④ 서버 검증→새 페이지 복원: 위치 {t2}, 모양 {sorted(set(l2.values()))}'); pg2.close()
    # ⑤ '기본'으로 되돌리면 전 장면에서 모양이 빠진다(위치는 남는다)
    show(1); pick('auto'); looks = look_of()
    need(not any(v is not None for v in looks.values()), f'⑤ 기본으로 되돌리면 전 장면 모양 해제 {looks}')
    show(2); need(abs(top() - moved) <= 1, '⑤ 되돌려도 3번째 장면 위치는 유지')
    need(not errs, f'페이지 오류 {errs[:3]}'); b.close()
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
