# 획 미리보기 시트(획만) — py stroke_sheet.py out.png [--order] : hero_strokes.js 의 획을 그려 5열 시트로
# --order: 획 순서를 색으로(앞=파랑 → 뒤=빨강) — 몸부터 긋는 그림 찾기
import sys, os, json, re
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
js = open(os.path.join(HERE, "hero_strokes.js"), encoding="utf-8").read()
D = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
out = sys.argv[1]; order = "--order" in sys.argv
cols, cell = 5, 200; names = list(D); rows = (len(names) + cols - 1) // cols
sh = Image.new("RGB", (cols * cell, rows * (cell + 18)), "white"); d = ImageDraw.Draw(sh); F = ImageFont.truetype("malgun.ttf", 12)
for k, n in enumerate(names):
    im = Image.new("RGB", (1024, 1024), "white"); g = ImageDraw.Draw(im); P = D[n]["paths"]
    for i, p in enumerate(P):
        pts = [(int(a), int(b)) for a, b in re.findall(r"(-?\d+) (-?\d+)", p)]
        c = (int(255 * i / len(P)), 0, int(255 * (1 - i / len(P)))) if order else (0, 0, 0)
        g.line(pts, fill=c, width=4)
    x, y = (k % cols) * cell, (k // cols) * (cell + 18)
    sh.paste(im.resize((cell, cell), Image.LANCZOS), (x, y + 18)); d.text((x + 3, y + 2), f"{n} {len(P)}", fill="black", font=F)
sh.save(out); print(out)
