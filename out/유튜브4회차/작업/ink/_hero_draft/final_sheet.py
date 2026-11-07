# 15장 완성 미리보기: 종이색 위 flat 컬러판(0.9) × 원본 선(multiply 근사) — py final_sheet.py out.png
import os, sys, json, numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); A = json.load(open(os.path.join(HERE, "hero_anchor.json"), encoding="utf-8"))
F = ImageFont.truetype("malgun.ttf", 12); cols, cell = 5, 200; names = list(A)
sh = Image.new("RGB", (cols * cell, 3 * (cell + 16)), "white"); d = ImageDraw.Draw(sh)
for i, n in enumerate(names):
    b = n[2:]; paper = np.full((1024, 1024, 3), (0xFB, 0xF8, 0xF1), np.float32)
    fp = os.path.join(HERE, f"c_{b}_flat.png")
    if os.path.exists(fp):
        c = np.array(Image.open(fp).convert("RGBA"), np.float32); al = c[..., 3:] / 255 * 0.9
        paper = paper * (1 - al) + paper * (c[..., :3] / 255) * al
    l = np.array(Image.open(os.path.join(HERE, f"l_{b}.png")), np.float32); la = l[..., 3:] / 255
    out = paper * (1 - la) + l[..., :3] * la
    im = Image.fromarray(out.clip(0, 255).astype(np.uint8)).resize((cell, cell), Image.LANCZOS)
    x, y = (i % cols) * cell, (i // cols) * (cell + 16); sh.paste(im, (x, y + 16)); d.text((x + 3, y + 1), n + ("" if os.path.exists(fp) else " (컬러 없음)"), fill="black", font=F)
sh.save(sys.argv[1]); print(sys.argv[1])
