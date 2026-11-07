# 눈·정수리·턱 측정값 확인 시트 — hero_anchor.json 값을 얼굴 확대 위에 표시(빨강=눈 사이, 파랑=정수리, 초록=턱, 눈금 32px)
# 쓰기: py anchor_sheet.py out.png [이름 ...]
import sys, os, json
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(HERE, "hero_anchor.json"), encoding="utf-8"))
out = sys.argv[1]; names = sys.argv[2:] or list(A)
cols, cell, R = 5, 200, 200
rows = (len(names) + cols - 1) // cols
sh = Image.new("RGB", (cols * cell, rows * (cell + 18)), "white"); d = ImageDraw.Draw(sh)
F = ImageFont.truetype("malgun.ttf", 12)
for k, n in enumerate(names):
    a = A[n]; im = Image.open(os.path.join(HERE, n + ".png")).convert("RGB"); g = ImageDraw.Draw(im)
    cx, cy = a["ex"], (a["top"] + a["chin"]) // 2
    for v in range(0, 1024, 32):
        g.line([(v, 0), (v, 1024)], fill=(255, 215, 215)); g.line([(0, v), (1024, v)], fill=(255, 215, 215))
    g.line([(a["ex"] - 60, a["ey"]), (a["ex"] + 60, a["ey"])], fill=(255, 0, 0), width=2); g.ellipse([a["ex"] - 5, a["ey"] - 5, a["ex"] + 5, a["ey"] + 5], outline=(255, 0, 0), width=2)
    g.line([(cx - 90, a["top"]), (cx + 90, a["top"])], fill=(0, 0, 255), width=2)
    g.line([(cx - 90, a["chin"]), (cx + 90, a["chin"])], fill=(0, 170, 0), width=2)
    crop = im.crop((cx - R, cy - R, cx + R, cy + R)).resize((cell, cell), Image.LANCZOS)
    x, y = (k % cols) * cell, (k // cols) * (cell + 18)
    sh.paste(crop, (x, y + 18)); d.text((x + 3, y + 2), n, fill="black", font=F)
sh.save(out); print(out)
