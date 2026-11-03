"""P6~P10 검사 도구 (Opus 실행, 2026-10-29).
usage: py check.py P6 [--tag after] [--video out_v1.mp4]
 - 0.5초 간격 프레임 → 잉크 비율(종이 #FBF8F1 과 채널차 >30 인 픽셀 비율)
 - 잉크 5% 미만 프레임 수, 4x4 칸(480x270) 중 연속 빈칸(잉크<1%) 최장 초
 - 0.5초 시트(긴 변 1000px) 저장: <장면>/sheet_<tag>.jpg
"""
import sys, subprocess, pathlib, math, tempfile, json
import numpy as np
from PIL import Image
HQ = pathlib.Path(__file__).resolve().parent.parent
sc = sys.argv[1]; tag = 'after'; vid = 'out.mp4'
a = sys.argv[2:]
if '--tag' in a: tag = a[a.index('--tag') + 1]
if '--video' in a: vid = a[a.index('--video') + 1]
d = HQ / sc; tmp = pathlib.Path(tempfile.mkdtemp())
subprocess.run(['ffmpeg', '-v', 'error', '-i', str(d / vid), '-vf', 'fps=2', str(tmp / 'f%03d.png')], check=True)
fr = sorted(tmp.glob('f*.png'))
paper = np.array([251, 248, 241], dtype=np.int16)
inks = []; cells = []
for f in fr:
    im = np.asarray(Image.open(f).convert('RGB'), dtype=np.int16)
    m = (np.abs(im - paper).max(axis=2) > 30)
    inks.append(float(m.mean()))
    H, W = m.shape
    cells.append([[float(m[r*H//4:(r+1)*H//4, c*W//4:(c+1)*W//4].mean()) for c in range(4)] for r in range(4)])
# 2x2 칸(=화면 4분할의 4x4 중 인접 2x2 블록, 480x270 단위가 아니라 960x540 블록 9개) 대신 판정서 정의대로 480x270 한 칸 기준
longest = 0.0; where = None
for r in range(4):
    for c in range(4):
        run = 0
        for i, cl in enumerate(cells):
            run = run + 1 if cl[r][c] < 0.01 else 0
            if run * 0.5 > longest: longest = run * 0.5; where = (r, c, i * 0.5)
# 2x2 블록(960x540) 연속 빈 초
long2 = 0.0; where2 = None
for r in range(3):
    for c in range(3):
        run = 0
        for i, cl in enumerate(cells):
            v = (cl[r][c] + cl[r][c+1] + cl[r+1][c] + cl[r+1][c+1]) / 4
            run = run + 1 if v < 0.01 else 0
            if run * 0.5 > long2: long2 = run * 0.5; where2 = (r, c, i * 0.5)
low = [round(i * 0.5, 1) for i, v in enumerate(inks) if v < 0.05]
# 시트
ims = [Image.open(f) for f in fr]; cols = 6; rows = math.ceil(len(ims) / cols)
tw = 1000 // cols; th = int(tw * 1080 / 1920)
sh = Image.new('RGB', (cols * tw, rows * th), 'white')
for i, im in enumerate(ims):
    t = im.resize((tw - 2, th - 2)); sh.paste(t, ((i % cols) * tw, (i // cols) * th))
sh.save(d / f'sheet_{tag}.jpg', quality=85)
res = {'scene': sc, 'tag': tag, 'frames': len(fr), 'ink_lt5': len(low), 'low_at': low,
       'ink': [round(v * 100, 1) for v in inks], 'cell_empty_max_s': longest, 'cell_at': where,
       'block2x2_empty_max_s': long2, 'block_at': where2}
print(json.dumps(res, ensure_ascii=False))
(d / f'check_{tag}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf8')
