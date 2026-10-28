# -*- coding: utf-8 -*-
"""실제 편집기(out/scene-style-ui-showcase.html)에서 폰트 세트를 하나씩 '눌러서' 잰다 — 목업이 아니라 고객이 보는 화면.

  py tools/scene_font_research/check_editor_fonts.py <출력폴더> [--all]     (8773 서버 필요. --all = 기존 세트까지)
잰 것: ①그 글꼴이 진짜 로드돼 쓰였나(폴백 아님) ②띄어쓰기 폭 ③? ! , 가 제 글꼴로 나오나 ④제목이 칸을 넘나 ⑤글자 높이(글꼴 간 편차)
결과: 표 + 편집기 화면을 그대로 모은 contact sheet(editor_fonts.png)
"""
import sys, json, pathlib
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
URL = 'http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1'
T1, T2 = '이거 진짜, 미쳤다?!', '일본 천재의 발명품'

MEASURE = """([t1,t2])=>{
  const c=document.createElement('canvas').getContext('2d');
  return [...document.querySelectorAll('#a-live-preview .precision-text')].filter(e=>['hook1','hook2','channel','bodyTitle'].includes(e.dataset.editBind)).map(e=>{
    const cs=getComputedStyle(e),fam=cs.fontFamily.split(',')[0].replace(/"/g,'').trim(),px=parseFloat(cs.fontSize),txt=e.textContent;
    const w=(f,s)=>{c.font=`100px ${f}`;return c.measureText(s).width};
    const r=document.createRange();r.selectNodeContents(e);const tw=r.getBoundingClientRect().width,bw=e.getBoundingClientRect().width;
    const m=(c.font=`100px "${fam}"`,c.measureText('건망증환자'));
    const xs=parseFloat((cs.transform.match(/matrix\\(([^,]+)/)||[])[1]||1);
    return {bind:e.dataset.editBind,fam,px:+px.toFixed(1),xscale:+xs.toFixed(2),
      loaded:document.fonts.check(`40px "${fam}"`,txt),
      fallback:(()=>{  // 폭 비교는 못 쓴다 — 한글은 글꼴이 달라도 전각 폭이 같다(잘난체가 오탐). 실제 그린 픽셀을 기본 글꼴과 비교한다
        const ink=f=>{const k=document.createElement('canvas');k.width=360;k.height=90;const x=k.getContext('2d');x.font=`60px ${f}`;x.textBaseline='top';x.fillText('건망증환',4,8);return x.getImageData(0,0,360,90).data};
        const a=ink(`"${fam}",sans-serif`),b=ink('sans-serif');let diff=0;for(let i=3;i<a.length;i+=4)if(Math.abs(a[i]-b[i])>40)diff++;return diff<60})(),
      space:+(w(`"${fam}"`,'가 가')-w(`"${fam}"`,'가가')).toFixed(1),
      punctOwn:Math.abs(w(`"${fam}"`,'?!,')-w('sans-serif','?!,'))>.01,
      over:tw>bw+2.5, clip:e.scrollHeight>e.clientHeight+4, lines:Math.round(r.getBoundingClientRect().height/(parseFloat(cs.lineHeight)||px*1.18)), ink:+(px*(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent)/100).toFixed(1)}})}"""

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 1000}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); bad = []; pg.on('response', lambda r: bad.append((r.status, r.url[-60:])) if r.status >= 400 else None)
    pg.goto(URL, wait_until='networkidle'); pg.click('[data-left-tab="font"]')
    sets = pg.evaluate("[...document.querySelectorAll('[data-font-set]')].map(e=>[e.dataset.fontSet,e.textContent.trim().split('\\n').pop().trim()])")
    if '--all' not in sys.argv:
        sets = [s for s in sets if s[0].startswith('f') and s[0][1:].isdigit()]
    # 문구를 실제 입력칸으로 바꾼다(고객과 같은 길). 입력칸을 못 찾으면 저장값으로 넣는다.
    snap = pg.evaluate('window.sceneStyle.snapshot()'); snap['text'].update({'hook1': T1, 'hook2': T2})
    pg.evaluate('s=>window.sceneStyle.load(window.sceneStyle.context(),s)', snap); pg.click('[data-left-tab="font"]')
    rows, shots = [], []
    for sid, label in sets:
        pg.click(f'[data-font-set="{sid}"]'); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(450)
        m = pg.evaluate(MEASURE, [T1, T2]); rows.append((sid, m))
        shot = out / f'ed_{sid or "default"}.png'; pg.locator('#a-live-preview').screenshot(path=str(shot)); shots.append((sid, shot))
    names = dict(pg.evaluate("[...document.querySelectorAll('[data-font-set]')].map(e=>[e.dataset.fontSet,(e.querySelector('.fs-name')||e.lastElementChild).textContent.trim()])"))
    b.close()

print(f'{"세트":8s} {"이름":16s} 로드 폴백 공백폭 부호  넘침  1줄px  2줄px  1줄잉크')
fails = []
for sid, m in rows:
    h1 = next(x for x in m if x['bind'] == 'hook1'); h2 = next(x for x in m if x['bind'] == 'hook2'); bt = next((x for x in m if x['bind'] == 'bodyTitle'), None)
    prob = [k for k, v in (('미로드', not h1['loaded']), ('폴백', h1['fallback']), ('공백0', h1['space'] <= 1), ('부호폴백', not h1['punctOwn']), ('넘침', h1['over'] or h2['over']), ('본문제목 잘림', bt and bt['clip'])) if v]
    if prob: fails.append((names.get(sid, sid), prob))
    print(f"{sid:8s} {names.get(sid, '')[:14]:16s} {'O' if h1['loaded'] else 'X':3s} {'X' if h1['fallback'] else '-':3s} {h1['space']:6.1f} {'O' if h1['punctOwn'] else 'X':3s} {'넘침' if (h1['over'] or h2['over']) else '-':4s} {h1['px']:6.1f} {h2['px']:6.1f} {h1['ink']:7.1f}  x{h1['xscale']}")
inks = [next(x for x in m if x['bind'] == 'hook1')['ink'] for _, m in rows]
print(f'\n글꼴 {len(rows)}종 | 1줄 글자 높이 최대/최소 = {max(inks) / min(inks):.3f}배 ({min(inks)}~{max(inks)}px) | 문제 {fails or "없음"}')
print('페이지 오류', errs[:3], '| 실패 응답', bad[:3])

# 편집기 화면 그대로 모은 표(위쪽 45%만)
cols, W = 6, 300
tiles = []
for sid, shot in shots:
    im = Image.open(shot).convert('RGB'); w, h = im.size; im = im.crop((0, 0, w, int(h * .47))); im = im.resize((W, int(im.size[1] * W / w)))
    tiles.append((names.get(sid, sid), im))
th = max(t.size[1] for _, t in tiles) + 26; rowsn = -(-len(tiles) // cols)
sheet = Image.new('RGB', (cols * (W + 8), rowsn * (th + 8)), (14, 16, 20)); d = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype('malgun.ttf', 15)
except Exception: font = ImageFont.load_default()
for i, (nm, t) in enumerate(tiles):
    x, y = (i % cols) * (W + 8), (i // cols) * (th + 8); sheet.paste(t, (x, y)); d.text((x + 4, y + t.size[1] + 3), nm, fill=(220, 225, 235), font=font)
sheet.save(out / 'editor_fonts.png'); print('모음 그림', out / 'editor_fonts.png', sheet.size)
