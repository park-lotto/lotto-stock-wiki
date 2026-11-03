# Q 장면 자가 검사 — 0.5초 간격 프레임 → 잉크·칸 비움·시트 + (미리보기 모드) 타이밍 규칙 R4·R5
# usage: py qcheck.py Q1 [--video out.mp4] [--step 0.5] [--face t,x,y,w]
#   기본 = 브라우저 미리보기(template/index.html 을 __S.render(t) 로 찍음, 렌더 없이 빠름)
#   --video 파일 = 실제 렌더 결과에서 프레임을 뽑아 잰다(최종 판정용)
import sys, os, json, subprocess, tempfile, argparse
from PIL import Image, ImageDraw, ImageChops
import numpy as np
HQ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('scene'); ap.add_argument('--video'); ap.add_argument('--step', type=float, default=0.5)
ap.add_argument('--face'); ap.add_argument('--tag', default='')
a = ap.parse_args()
D = os.path.join(HQ, a.scene); dur = float(open(os.path.join(D, 'dur.txt')).read().strip())
ts = [round(i * a.step, 2) for i in range(int(dur / a.step) + 1) if i * a.step < dur - 1e-6]
frames = {}; timing = None
extra = [float(a.face.split(',')[0])] if a.face else []
if a.video:
    tmp = tempfile.mkdtemp()
    for t in ts + [dur - 1.0, dur - 0.04] + extra:
        p = os.path.join(tmp, f'{t:.2f}.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', a.video, '-frames:v', '1', p], check=True)
        frames[t] = Image.open(p).convert('RGB')
else:
    from playwright.sync_api import sync_playwright
    url = 'file:///' + os.path.join(D, 'template', 'index.html').replace('\\', '/')
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome'); pg = b.new_page(viewport={'width': 1920, 'height': 1080})
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(url); pg.wait_for_function('window.__S', timeout=20000)
        if errs: print('PAGE ERRORS:', errs)
        for t in ts + [dur - 1.0, dur - 0.04] + extra:
            pg.evaluate(f'__S.render({t})')
            frames[t] = Image.open(__import__('io').BytesIO(pg.locator('#stage').screenshot())).convert('RGB')
        timing = pg.evaluate('''() => {
          const S = __S, vis = (L) => { let a = 1; for (let x = L; x; x = x.parent) { if (x.stat) return false; } return true; };
          return { texts: S.texts.map(T => ({ x0: T.x, x1: T.x + T.w, s: T.s, e: T.end, str: T.chars.map(c => c.sp.textContent).join(''), size: T.size, stat: T.L.stat })),
                   pens: S.items.filter(i => i.pen && i.s >= 0).map(i => ({ s: i.s, e: i.s + i.dur, c: i.el.getAttribute('stroke'), w: +i.el.getAttribute('stroke-width') })),
                   lines: S.items.filter(i => i.s >= 0).map(i => ({ s: i.s, e: i.s + i.dur, c: i.el.getAttribute('stroke') })) }; }''')
        b.close()
PAPER = np.array([0xFB, 0xF8, 0xF1])
def inkmask(im):
    x = np.asarray(im.resize((480, 270))).astype(int)
    return (np.abs(x - PAPER).max(axis=2) > 40)
rows = []; masks = {}
for t in ts:
    m = inkmask(frames[t]); masks[t] = m; rows.append((t, m.mean() * 100))
low = [t for t, v in rows if v < 5]
# 4x4 칸(480x270) 비움 연속 시간
G = 4; empty_run = {}
for gy in range(G):
    for gx in range(G):
        run = best = 0
        for t in ts:
            c = masks[t][gy * 270 // G:(gy + 1) * 270 // G, gx * 480 // G:(gx + 1) * 480 // G]
            if c.mean() < 0.01: run += a.step; best = max(best, run)
            else: run = 0
        empty_run[(gx, gy)] = best
bad_cells = {f'{k[0]},{k[1]}': v for k, v in empty_run.items() if v > 3.0}
still = np.asarray(ImageChops.difference(frames[dur - 1.0], frames[dur - 0.04]).convert('L')).astype(int)
moving = int((still > 24).sum())
print(f'[{a.scene}] {"video" if a.video else "preview"} frames={len(ts)} ink<5%: {len(low)} {low}')
print('ink%:', ' '.join(f'{t:g}:{v:.0f}' for t, v in rows))
print('cells empty >3s:', bad_cells or 'none')
print(f'last 1.0s moving pixels: {moving}')
if timing:
    T = timing['texts']; P = timing['pens']; issues = []
    act = [('T:' + x['str'], x['s'], x['e']) for x in T if x['s'] >= 0] + [('L', x['s'], x['e']) for x in P]
    act.sort(key=lambda z: z[1])
    for i in range(len(act)):
        for j in range(i + 1, len(act)):
            if act[j][1] >= act[i][2] - 1e-3: break
            if act[i][0].startswith('T') or act[j][0].startswith('T'):
                issues.append(f'{act[i][0]}[{act[i][1]:.2f}-{act[i][2]:.2f}] x {act[j][0]}[{act[j][1]:.2f}-{act[j][2]:.2f}]')
    print('R5 text overlaps:', len(issues)); [print('  ', s) for s in issues[:12]]
    for x in T:
        if x['x0'] < 30 or x['x1'] > 1890: print(f'  TEXT OUT OF FRAME: {x["str"]} x {x["x0"]:.0f}..{x["x1"]:.0f}')
    big = [x for x in T if x['s'] >= 0]
    last = max(big, key=lambda x: x['e']) if big else None
    org = [x for x in timing['lines'] if (x['c'] or '').upper() == '#F6A93B']
    lastorg = max([x['e'] for x in org], default=0)
    lastany = max([x['e'] for x in timing['lines']] + [x['e'] for x in T], default=0)
    if last: print(f'R4 last text "{last["str"]}" {last["size"]}px ends {last["e"]:.2f} (limit {dur-2:.1f}) {"OK" if last["e"] <= dur-2 + 1e-6 else "FAIL"}')
    print(f'R4 last orange mark ends {lastorg:.2f} (limit {dur-1.2:.1f}) {"OK" if lastorg <= dur-1.2 + 1e-6 else "FAIL"} / last drawing ends {lastany:.2f} (static from {dur-1:.1f})')
# 시트(긴 변 1000 이하): 5열
cols = 5; tw, th = 200, 112; n = len(ts); rws = (n + cols - 1) // cols
sh = Image.new('RGB', (cols * tw, rws * th), 'white'); dr = ImageDraw.Draw(sh)
for i, t in enumerate(ts):
    im = frames[t].resize((tw - 2, th - 2)); sh.paste(im, ((i % cols) * tw, (i // cols) * th))
    dr.text(((i % cols) * tw + 3, (i // cols) * th + 2), f'{t:g}', fill=(220, 40, 40))
out = os.path.join(D, f'qsheet{a.tag}.jpg'); sh.save(out, quality=85); print('sheet', out, sh.size)
if a.face:
    t, x, y, w = [float(v) for v in a.face.split(',')]
    key = min(frames, key=lambda k: abs(k - t))
    im = frames[key] if abs(key - t) < 0.01 else None
    if im is None and a.video:
        p = os.path.join(tempfile.mkdtemp(), 'f.png'); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', a.video, '-frames:v', '1', p]); im = Image.open(p).convert('RGB')
    cr = im.crop((int(x), int(y), int(x + w), int(y + w * 9 / 16))).resize((960, 540))
    fo = os.path.join(D, f'qface{a.tag}.jpg'); cr.save(fo, quality=88); print('face', fo)
json.dump({'low': low, 'ink': rows, 'cells': bad_cells, 'moving': moving}, open(os.path.join(D, f'qcheck{a.tag}.json'), 'w'))
