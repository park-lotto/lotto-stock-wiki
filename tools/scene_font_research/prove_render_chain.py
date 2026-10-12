# -*- coding: utf-8 -*-
"""글꼴·색톤이 '편집기 화면 → 저장값 → 서버 검증 → 진짜 렌더러 PNG'까지 그대로 가는지 실제로 돌려 본다.
   py tools/scene_font_research/prove_render_chain.py <출력폴더> [fontSetId] [바탕색] [1줄색] [2줄색]
   (8773 서버 필요. 렌더러는 shopping_shorts.scene_style.render_layers가 쓰는 tools/render_scene_style.js 그대로)"""
import sys, json, pathlib, subprocess
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
fid, bg, c1, c2 = (sys.argv[2:6] + ['f330', '#17101A', '#FFFFFF', '#FF5FA8'][len(sys.argv) - 2:])[:4]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 1000}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    look = fid.startswith('look:')
    if look: pg.click('[data-left-tab="look"]'); pg.click(f'[data-look="{fid[5:]}"]')     # 추천 룩 카드 한 번
    else: pg.click('[data-left-tab="font"]'); pg.click(f'[data-font-set="{fid}"]')          # 고객이 누르는 그 버튼
    for key, val in (() if look else (('top', bg), ('title1', c1), ('title2', c2))):                      # 고객이 만지는 그 색상칸
        pg.evaluate("([k,v])=>{const i=document.querySelector(`[data-fixed-color=\"${k}\"]`);i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}))}", [key, val])
    pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(600)
    used = pg.evaluate("()=>[...document.querySelectorAll('#a-live-preview .precision-text')].map(e=>[e.dataset.editBind,getComputedStyle(e).fontFamily.split(',')[0],getComputedStyle(e).color,e.textContent.trim().slice(0,12)])")
    print('편집기 화면의 실제 글꼴·색:'); [print('  ', u) for u in used]
    print('글꼴 로드 대기 끝:', pg.evaluate('document.fonts.status'))
    pg.locator('#a-live-preview').screenshot(path=str(out / 'A_editor.png'))
    snap = pg.evaluate('window.sceneStyle.snapshot()'); print('페이지 오류', errs); b.close()
snap = scene_style.validate_snapshot(snap)                                              # 서버가 저장 전에 돌리는 그 검증
print('서버 검증 통과 → 남은 값: fontSet=', snap.get('fontSet'), '| titleDeco=', snap.get('titleDeco'), '| fixedColors=', snap.get('fixedColors'), '| colors=', snap.get('colors'))
ctx = {'jobId': None, 'text': snap['text'], 'scenes': [
    {'start': 0, 'end': 1.5, 'caption': '', 'caption_visible': True, 'beat_idx': 0, 'kind': 'hook'},
    {'start': 1.5, 'end': 3, 'caption': '전 세계 건망증 환자들의', 'caption_visible': True, 'beat_idx': 1, 'kind': 'body'}]}
snap['hookMotion'] = 'zoom-punch'
(out / 'scene-style-request.json').write_text(json.dumps({'snapshot': snap, 'context': ctx, 'output': str(out)}, ensure_ascii=False), encoding='utf-8')
r = subprocess.run(['node', str(ROOT / 'tools/render_scene_style.js'), str(out / 'scene-style-request.json')], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
print('렌더러 rc=', r.returncode, r.stderr[-400:]); print(sorted(x.name for x in out.glob('scene-style-layer-*.png')))
