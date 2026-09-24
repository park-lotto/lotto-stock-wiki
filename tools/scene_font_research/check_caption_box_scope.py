# -*- coding: utf-8 -*-
"""자막박스 너비·높이·박스색·글자색·투명도가 [모든 장면|이 장면만] 스위치를 따르는지 (2026-09-24 고객 데이워커님 제보).
  "자막박스 모양 시 모든 장면이 선택되어 있어도 전체 장면에 적용되지 않고 있네요 / 자막박스에 투명도까지"
  py tools/scene_font_research/check_caption_box_scope.py <출력폴더>      (8773 서버 필요)
고치기 전 코드: 스위치가 '모양' 버튼에만 걸려 있고 크기·색 칸은 늘 지금 장면에만 저장됐다 → ①이 실패한다. 투명도 칸은 아예 없었다 → ③ 실패.
썰쇼핑형(story)·전장면 고정형(continuous) 둘 다 본다.
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
PATCH = "#a-live-preview .precision-patch[data-edit-bind=caption]"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for mode in ('story', 'continuous'):
        print(f'── {mode}')
        pg = b.new_page(viewport={'width': 1600, 'height': 1600}); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
        if mode == 'continuous':
            pg.evaluate("()=>{document.querySelector('[data-template-mode=\"continuous\"]').click();return 1}"); pg.wait_for_timeout(1200)
        total = pg.evaluate("(()=>{for(const e of document.querySelectorAll('body *')){const m=e.childElementCount===0&&e.textContent.trim().match(/^\\d+\\s*\\/\\s*(\\d+)$/);if(m)return +m[1]}return 0})()")
        assert total > 3, '장면 수를 못 읽었다'
        show = lambda i: (pg.evaluate(f'window.sceneStyle.show({i})'), pg.wait_for_timeout(250))
        first = 1 if mode == 'story' else 0   # 썰쇼핑형 0번은 훅(자막 칸 없음)
        def open_panel():
            pg.evaluate("()=>{const s=document.querySelector('[data-caption-look-scope]');for(let e=s;e;e=e.parentElement){if(e.tagName==='DETAILS')e.open=true;if(e.hidden)e.hidden=false}return 1}")
        def scope(v): open_panel(); pg.click(f'[data-caption-look-scope="{v}"]'); pg.wait_for_timeout(150)
        def put(key, val):   # 고객이 슬라이더를 끌거나 색을 고른 것과 같게 input 이벤트를 낸다
            open_panel()
            ok = pg.evaluate("([k,v])=>{const i=document.querySelector(`[data-caption-layout=\"${k}\"]`);if(!i)return false;i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));return true}", [key, val])
            pg.wait_for_timeout(200); return ok
        layouts = lambda: {int(k.split(':')[2]): v for k, v in pg.evaluate('window.sceneStyle.snapshot()')['captionLayouts'].items() if f':{mode}:' in k}
        paint = lambda: pg.evaluate(f"(()=>{{const e=document.querySelector('{PATCH}');if(!e)return null;const c=getComputedStyle(e);return [c.backgroundColor,c.opacity,Math.round(e.getBoundingClientRect().height)]}})()")
        others = [i for i in range(first, total) if i != first + 1]
        show(first + 2); before = paint()
        # ① '모든 장면'에서 박스색·높이를 바꾸면 전 장면이 바뀐다
        show(first + 1); scope('all')
        put('background', '#ff2266'); put('h', '14')
        L = layouts()
        need(all(L.get(i, {}).get('background') == '#ff2266' and L.get(i, {}).get('h') == 14 for i in range(first, total)),
             f'① 모든 장면: 박스색·높이가 전 장면 저장값에 들어간다 { {i: (L.get(i, {}).get("background"), L.get(i, {}).get("h")) for i in range(first, total)} }')
        show(first + 2); after = paint()
        need(after and after[0] == 'rgb(255, 34, 102)' and after[2] > before[2], f'① 다른 장면 화면에서도 박스색·높이가 바뀐다 {before} → {after}')
        # ② 글자색도
        show(first + 1); put('color', '#00ff00'); L = layouts()
        need(all(L.get(i, {}).get('color') == '#00ff00' for i in range(first, total)), '② 모든 장면: 자막 글자색도 전 장면')
        # ③ 투명도 칸이 있고, 모든 장면에 먹는다
        show(first + 1); has = put('boxClear', '60'); L = layouts()
        need(has, '③ 자막박스 투명도 칸이 있다')
        need(has and all(L.get(i, {}).get('boxClear') == 60 for i in range(first, total)), f'③ 투명도 60%가 전 장면에 { {i: L.get(i, {}).get("boxClear") for i in range(first, total)} }')
        show(first + 2); op = paint()
        need(op and abs(float(op[1]) - 0.4) < 0.01, f'③ 다른 장면 화면에서 박스가 40% 진하기로 보인다 {op}')
        # ④ '이 장면만'이면 그 장면만
        scope('one'); show(first + 3); put('background', '#112233'); L = layouts()
        need(L.get(first + 3, {}).get('background') == '#112233' and all(L.get(i, {}).get('background') == '#ff2266' for i in range(first, total) if i != first + 3),
             '④ 이 장면만: 다른 장면 박스색은 그대로')
        # ⑤ 서버 검증을 통과하고, 새 페이지에서 불러와도 투명도가 남는다
        snap = pg.evaluate('window.sceneStyle.snapshot()')
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from shopping_shorts import scene_style
        try: v = scene_style.validate_snapshot(json.loads(json.dumps(snap))); okv = True
        except Exception as e: okv = False; print('  서버 검증 오류', e)
        need(okv, '⑤ 서버 검증 통과')
        if okv:
            pg2 = b.new_page(viewport={'width': 1600, 'height': 1600}); pg2.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
            pg2.evaluate('s=>window.sceneStyle.load(window.sceneStyle.context(),s)', v); pg2.evaluate(f'window.sceneStyle.show({first + 2})'); pg2.wait_for_timeout(500)
            op2 = pg2.evaluate(f"getComputedStyle(document.querySelector('{PATCH}')).opacity")
            need(abs(float(op2) - 0.4) < 0.01, f'⑤ 새 페이지 복원 후에도 투명도 유지 {op2}'); pg2.close()
        show(first + 2); pg.locator('#a-live-preview').screenshot(path=str(out / f'caption_box_{mode}.png'))
        pg.close()
    need(not errs, f'페이지 오류 {errs[:3]}'); b.close()
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
