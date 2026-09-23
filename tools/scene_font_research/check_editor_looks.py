# -*- coding: utf-8 -*-
"""실제 편집기의 [추천|장면|폰트|색톤|꾸밈] 탭을 고객처럼 눌러서 검사한다.

  py tools/scene_font_research/check_editor_looks.py <출력폴더>      (8773 서버 필요)
① 추천 24개를 하나씩 클릭 → 화면의 글꼴·색·꾸밈이 그 룩이 가리키는 값인가, 제목이 칸을 넘나
② 저장값(snapshot) → 서버 검증(validate_snapshot) 통과 후에도 fontSet·titleDeco·fixedColors(훅+본문)가 남나
③ 그 저장값을 새 페이지에서 load → 같은 화면으로 돌아오나(재접속 복원)
④ 색톤·꾸밈 탭 단독 클릭, '원래 색'·'꾸밈 없음'으로 되돌리기
결과: 표 + 편집기 화면 모음(editor_looks.png)
"""
import sys, json, pathlib
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
URL = 'http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1'
T1, T2 = '이거 진짜, 미쳤다?!', '일본 천재의 발명품'
STATE = """()=>{const q=b=>document.querySelector(`#a-live-preview .precision-text[data-edit-bind="${b}"]`),rgb=c=>'#'+c.match(/\\d+/g).slice(0,3).map(n=>(+n).toString(16).padStart(2,'0')).join('').toUpperCase();
  const h1=q('hook1'),h2=q('hook2'),ink=h2.querySelector('.title-deco-ink'),r=e=>{const g=document.createRange();g.selectNodeContents(e);return g.getBoundingClientRect().width>e.getBoundingClientRect().width+2.5};
  return {fam:getComputedStyle(h1).fontFamily.split(',')[0].replace(/"/g,''),c1:rgb(getComputedStyle(h1).color),c2:rgb(getComputedStyle(h2).color),deco:!!ink,decoCss:ink?ink.style.cssText:'',over:r(h1)||r(h2),t1:h1.textContent,t2:h2.textContent}}"""
fails = []
def need(ok, msg):
    if not ok: fails.append(msg)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 1000}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(URL, wait_until='networkidle')
    tabs = pg.evaluate("[...document.querySelectorAll('[data-left-tab]')].map(b=>[b.dataset.leftTab,b.textContent,Math.round(b.getBoundingClientRect().width),b.scrollWidth>b.clientWidth+1])")
    print('탭', tabs); need([t[0] for t in tabs] == ['mine', 'look', 'scene', 'font', 'tone', 'deco'], '탭 6개 순서(내 프리셋 맨 앞)'); need(not any(t[3] for t in tabs), '탭 글자 잘림')
    tops = pg.evaluate("[...document.querySelectorAll('[data-left-tab]')].map(b=>Math.round(b.getBoundingClientRect().top))"); print('탭 세로 위치', tops); need(len(set(tops)) == 1, f'탭이 한 줄이 아님 {tops}')
    need(pg.evaluate("!document.querySelector('.preset-grid,[data-preset]')?.closest('[hidden]')"), '처음에 장면 템플릿이 안 보임')
    snap = pg.evaluate('window.sceneStyle.snapshot()'); snap['text'].update({'hook1': T1, 'hook2': T2}); pg.evaluate('s=>window.sceneStyle.load(window.sceneStyle.context(),s)', snap)
    looks = pg.evaluate("(()=>{document.querySelector('[data-left-tab=\"look\"]').click();return [...document.querySelectorAll('[data-look]')].map(e=>[e.dataset.look,e.querySelector('b').textContent])})()")
    defs = pg.evaluate("""()=>{const src=[...document.scripts].find(s=>s.src.includes('precision20-ui.js'));return fetch(src.src).then(r=>r.text()).then(t=>{const grab=n=>Function('return '+t.match(new RegExp('const '+n+'=(\\\\[[\\\\s\\\\S]*?\\\\n  \\\\]);'))[1])();
      return {looks:grab('LOOKS'),tones:grab('TONES'),fonts:Object.fromEntries(grab('FONT_SETS').map(f=>[f.id,f.title]))}})}""")
    tone_by = {t['id']: t for t in defs['tones']}; shots = []; saved = None
    print(f'{"룩":10s} 글꼴           1줄색    2줄색    꾸밈 넘침')
    for lid, name in looks:
        look = next(l for l in defs['looks'] if l['id'] == lid); tone = tone_by[look['tone']]
        pg.click(f'[data-look="{lid}"]'); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(400); s = pg.evaluate(STATE)
        boxlike = look['deco'] in ('box', 'under', 'grad')   # 글자색을 따로 칠하는 꾸밈 — color(=강조색)는 그대로여야 한다
        ok = s['fam'] == defs['fonts'][look['font']] and s['c1'] == tone['c1'].upper() and s['c2'] == tone['c2'].upper() and s['deco'] and not s['over'] and s['t1'] == T1
        need(ok, f'룩 {name}: {s} 기대 {defs["fonts"][look["font"]]} {tone["c1"]} {tone["c2"]}')
        print(f"{name:10s} {s['fam']:14s} {s['c1']:8s} {s['c2']:8s} {'O' if s['deco'] else 'X':3s} {'넘침' if s['over'] else '-'}  {'' if ok else '★불일치'}")
        shot = out / f'look_{lid}.png'; pg.locator('#a-live-preview').screenshot(path=str(shot)); shots.append((name, shot))
        sel = pg.evaluate("document.querySelectorAll('[data-look].selected').length"); need(sel == 1, f'룩 {name}: 선택 표시 {sel}개')
        if lid == 'l02': saved = pg.evaluate('window.sceneStyle.snapshot()'); saved_state = s; pg.locator('#a-live-preview').screenshot(path=str(out / 'reload_before.png'))
    # ② 서버 검증
    v = scene_style.validate_snapshot(json.loads(json.dumps(saved)))
    print('서버 검증 뒤:', 'fontSet=', v.get('fontSet'), 'titleDeco=', v.get('titleDeco'), 'fixedColors 키=', sorted(v.get('fixedColors', {})))
    need(v.get('titleDeco') == 'box' and v.get('fontSet') == 'f223' and sorted(v['fixedColors']) == ['t11:body', 't11:hook'], '서버 검증 뒤 값 유실')
    try: scene_style.validate_snapshot({**saved, 'titleDeco': '<script>'}); need(False, '나쁜 titleDeco가 통과됨')
    except ValueError as e: print('나쁜 titleDeco 거절:', e)
    # ③ 새 페이지에서 복원
    pg2 = b.new_page(viewport={'width': 1600, 'height': 1000}); pg2.on('pageerror', lambda e: errs.append('재접속:' + str(e))); pg2.goto(URL, wait_until='networkidle')
    pg2.evaluate('s=>window.sceneStyle.load(window.sceneStyle.context(),s)', v); pg2.evaluate('document.fonts.ready'); pg2.wait_for_timeout(600); s2 = pg2.evaluate(STATE)
    print('재접속 복원:', s2); need({k: s2[k] for k in ('fam', 'c1', 'c2', 'deco')} == {k: saved_state[k] for k in ('fam', 'c1', 'c2', 'deco')}, '재접속 뒤 화면이 다름')
    pg2.locator('#a-live-preview').screenshot(path=str(out / 'reload_after.png')); pg2.close()
    # ④ 색톤·꾸밈 단독 + 되돌리기
    pg.click('[data-left-tab="tone"]'); pg.click('[data-tone="p05"]'); pg.wait_for_timeout(300); a = pg.evaluate(STATE); need(a['c2'] == '#FF3B3B', f'색톤 단독 {a}')
    pg.click('[data-left-tab="deco"]'); pg.click('[data-deco="glow"]'); pg.wait_for_timeout(300); a = pg.evaluate(STATE); need('text-shadow' in a['decoCss'], f'꾸밈 단독 {a}')
    pg.click('[data-deco=""]'); pg.click('[data-left-tab="tone"]'); pg.click('[data-tone=""]'); pg.wait_for_timeout(300); a = pg.evaluate(STATE); sn = pg.evaluate('window.sceneStyle.snapshot()')
    print('되돌린 뒤:', a['c2'], '꾸밈', a['deco'], 'titleDeco=', repr(sn.get('titleDeco')), 'fixedColors=', sn.get('fixedColors')); need(a['c2'] == '#00F9ED' and not a['deco'] and not sn['fixedColors'], '되돌리기 실패')
    pg.click('[data-left-tab="scene"]'); need(pg.evaluate("[...document.querySelectorAll('.look-pane')].every(e=>e.hidden)"), '장면 탭에서 룩 창이 안 닫힘')
    b.close()
print('\n페이지 오류', errs[:5]); need(not errs, '페이지 오류')
print('실패', fails if fails else '없음')
cols, W = 6, 300; tiles = []
for nm, shot in shots:
    im = Image.open(shot).convert('RGB'); w, h = im.size; im = im.crop((0, 0, w, int(h * .47))); tiles.append((nm, im.resize((W, int(im.size[1] * W / w)))))
th = max(t.size[1] for _, t in tiles) + 26; sheet = Image.new('RGB', (cols * (W + 8), -(-len(tiles) // cols) * (th + 8)), (14, 16, 20)); d = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype('malgun.ttf', 15)
except Exception: font = ImageFont.load_default()
for i, (nm, t) in enumerate(tiles):
    x, y = (i % cols) * (W + 8), (i // cols) * (th + 8); sheet.paste(t, (x, y)); d.text((x + 4, y + t.size[1] + 3), nm, fill=(220, 225, 235), font=font)
sheet.save(out / 'editor_looks.png'); print('모음 그림', out / 'editor_looks.png')
sys.exit(1 if fails else 0)
