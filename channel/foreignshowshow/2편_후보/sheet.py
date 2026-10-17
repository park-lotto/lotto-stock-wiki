# -*- coding: utf-8 -*-
"""2편 후보 시트: sheet.py <mp4> <out.jpg> <start> <end> <step> [cols=8] [w=200]  (관제 097)"""
import subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw
mp4, out, s, e, st = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
cols = int(sys.argv[6]) if len(sys.argv) > 6 else 8
cw = int(sys.argv[7]) if len(sys.argv) > 7 else 200
tmp = Path(tempfile.mkdtemp())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s), "-t", str(e - s), "-i", mp4, "-vf", f"fps={1/st},scale={cw}:-2", str(tmp / "%04d.jpg")])
fr = sorted(tmp.glob("*.jpg"))
w, h = Image.open(fr[0]).size
rows = (len(fr) + cols - 1) // cols
sh = Image.new("RGB", (cols * w, rows * (h + 14)), "white"); d = ImageDraw.Draw(sh)
for i, f in enumerate(fr):
    x, y = i % cols * w, i // cols * (h + 14)
    sh.paste(Image.open(f), (x, y + 14)); d.text((x + 3, y + 1), f"{s + i * st:.0f}s", fill=(220, 0, 0))
sh.save(out, quality=82)
for f in fr: f.unlink()
tmp.rmdir()
print(out, len(fr))
