# 그림 모음 시트 — py hero_sheet.py out.png [--grid] [--cols 3] [--cell 330] 이름1 이름2 ...
# --grid: 64px 마다 옅은 눈금·128px 마다 숫자(1024 기준 좌표 읽기용)
import sys, os
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[1:]; out = a.pop(0); grid = "--grid" in a; a = [x for x in a if x != "--grid"]
cols, cell = 3, 330
if "--cols" in a: i = a.index("--cols"); cols = int(a[i+1]); del a[i:i+2]
if "--cell" in a: i = a.index("--cell"); cell = int(a[i+1]); del a[i:i+2]
rows = (len(a) + cols - 1) // cols
sh = Image.new("RGB", (cols * cell, rows * (cell + 22)), "white"); d = ImageDraw.Draw(sh)
try: F = ImageFont.truetype("malgun.ttf", 15)
except Exception: F = None
for k, n in enumerate(a):
    p = os.path.join(HERE, n if n.endswith(".png") else n + ".png")
    im = Image.open(p).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg.convert("RGB")
    if grid:
        g = ImageDraw.Draw(im); W = im.size[0]
        for v in range(64, W, 64):
            col = (255, 120, 120) if v % 128 == 0 else (255, 210, 210)
            g.line([(v, 0), (v, W)], fill=col, width=1); g.line([(0, v), (W, v)], fill=col, width=1)
            if v % 128 == 0:
                g.text((v + 2, 2), str(v), fill=(220, 0, 0), font=ImageFont.truetype("malgun.ttf", 22) if F else None)
                g.text((2, v + 2), str(v), fill=(220, 0, 0), font=ImageFont.truetype("malgun.ttf", 22) if F else None)
    im = im.resize((cell, cell), Image.LANCZOS)
    x, y = (k % cols) * cell, (k // cols) * (cell + 22)
    sh.paste(im, (x, y + 22)); d.text((x + 4, y + 2), n, fill="black", font=F)
sh.save(out); print(out, sh.size)
