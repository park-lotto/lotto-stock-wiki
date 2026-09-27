# -*- coding: utf-8 -*-
"""'내 프리셋 적용'이 자리(자막 끌어 옮김·제목 자리)까지 되살리나 (2026-09-25 사장님
 "프리셋 다른걸 누르면 스타일은 프리셋으로 바뀌는데 자리는 지금 자리로 된다").
  py tools/scene_font_research/check_my_preset_positions.py <출력폴더>      (8773 서버 필요)
고치기 전 코드: 프리셋이 자리를 안 담아 ②에서 자막이 지금 자리에 남는다 → 실패.
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
    names = iter(['A', 'B'])
    pg.on('dialog', lambda d: d.accept(next(names, 'X')) if d.type == 'prompt' else d.accept())
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    pg.evaluate("()=>{try{localStorage.removeItem('scene_style_my_presets')}catch(e){}return 1}")
    pg.click('[data-none]'); pg.wait_for_timeout(800)   # 원본 영상 그대로(인스타식)
    show = lambda i: (pg.evaluate(f'window.sceneStyle.show({i})'), pg.wait_for_timeout(300))
    top = lambda: pg.evaluate(f"(()=>{{const e=document.querySelector('{CAP}');const r=document.querySelector('#a-live-preview').getBoundingClientRect();return e?Math.round((e.getBoundingClientRect().top-r.top)/r.height*1000)/10:null}})()")
    def drag(dy):
        box = pg.locator(CAP).bounding_box(); x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x, y + dy, steps=8); pg.mouse.up(); pg.wait_for_timeout(300)
    def tab(t): pg.click(f'[data-left-tab="{t}"]'); pg.wait_for_timeout(200)
    show(2); default = top(); print('  기본 자막 자리', default, '%')
    drag(260); a_pos = top(); print('  프리셋 A 자리', a_pos, '%')
    need(a_pos and a_pos > default + 10, f'① 자막을 끌어 옮겼다 {default} → {a_pos}')
    tab('mine'); pg.click('[data-my-save]'); pg.wait_for_timeout(300)
    saved = pg.evaluate("()=>JSON.parse(localStorage.getItem('scene_style_my_presets')||'[]')")
    need(saved and saved[0].get('snap', {}).get('positions', {}).get('caption', {}).get('drag'), f'① 프리셋에 자리가 담겼다 {saved and saved[0]["snap"].get("positions")}')
    tab('scene'); show(2); drag(-420); moved = top(); print('  다른 자리로 옮김', moved, '%')
    tab('mine'); pg.click('[data-my-id] [data-my-apply]'); pg.wait_for_timeout(600)
    got = {}
    for i in (2, 5, 9): show(i); got[i] = top()
    need(all(v is not None and abs(v - a_pos) <= 0.6 for v in got.values()), f'② 프리셋 A 적용 → 자막이 A 자리로, 모든 장면 {got} (A {a_pos}, 옮긴 자리 {moved})')
    # ③ 자리를 안 담던 옛 프리셋 → 템플릿 기본 자리
    pg.evaluate("()=>{const l=JSON.parse(localStorage.getItem('scene_style_my_presets'));const o=JSON.parse(JSON.stringify(l[0]));o.id='old1';o.name='옛';delete o.snap.positions;l.unshift(o);localStorage.setItem('scene_style_my_presets',JSON.stringify(l));return 1}")
    tab('scene'); tab('mine'); pg.click('[data-my-id="old1"] [data-my-apply]'); pg.wait_for_timeout(600)
    show(2); old = top()
    need(old is not None and abs(old - default) <= 0.6, f'③ 자리 없는 옛 프리셋 → 기본 자리 {old} (기본 {default})')
    # ④ 저장값 서버 검증
    snap = pg.evaluate('window.sceneStyle.snapshot()')
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from shopping_shorts import scene_style
    try: scene_style.validate_snapshot(json.loads(json.dumps(snap))); ok = True
    except Exception as e: ok = False; print('   ', e)
    need(ok, '④ 적용 뒤 저장값이 서버 검증 통과')
    pg.locator('#a-live-preview').screenshot(path=str(out / 'after_apply.png'))
    # ⑤ 렌더(0순위-A1a): 프리셋 A를 다시 적용한 저장값으로 진짜 렌더러를 돌려 5번 장면 자막이 A 자리(≈67%)에 찍히나
    tab('scene'); tab('mine'); pg.click('[data-my-id]:not([data-my-id="old1"]) [data-my-apply]'); pg.wait_for_timeout(600)
    snapA = scene_style.validate_snapshot(json.loads(json.dumps(pg.evaluate('window.sceneStyle.snapshot()'))))
    # 샘플 작업대엔 job 컨텍스트가 없다(context()=null) — 화면의 '1 / 12' 표시에서 장면 수를 읽는다(check_caption_scope와 같다)
    n = pg.evaluate("(()=>{for(const e of document.querySelectorAll('body *')){const m=e.childElementCount===0&&e.textContent.trim().match(/^\d+\s*\/\s*(\d+)$/);if(m)return +m[1]}return 0})()")
    from shopping_shorts import video_assemble as va
    tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
    tl = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': f'자막 {i}번 문장입니다', 'caption_lines': [f'자막 {i}번 문장입니다'], 'tts_path': str(tts), 'target_seconds': 1,
           'role': 'hook' if i == 0 else 'body'} for i in range(n)]
    lay = scene_style.render_layers(tl, snapA, out / 'layers', {'text': '제목 첫줄' + chr(10) + '제목 둘째'}, 'mppqa')
    from PIL import Image
    im = Image.open(out / 'layers' / lay[5]['file']).convert('RGBA'); W, H = im.size
    rows = [y for y in range(0, H, 4) if sum(1 for x in range(int(W * .1), int(W * .9), 8) if im.getpixel((x, y))[3] > 40) > 5]
    band = [y / H * 100 for y in rows if y / H > .35]
    need(band and 60 <= min(band) <= 75, f'⑤ 렌더 레이어: 5번 장면 자막이 프리셋 자리(≈{a_pos}%)에 찍힌다 (찍힌 곳 {round(min(band),1) if band else None}~{round(max(band),1) if band else None}%)')
    need(not errs, f'페이지 오류 {errs[:3]}'); b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건'); sys.exit(1 if fails else 0)
