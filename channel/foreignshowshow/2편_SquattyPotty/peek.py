# -*- coding: utf-8 -*-
"""창(벤치 창 1080x1052 = 가로 원본 높이 맞춤 가운데 크롭) 그대로 잘라 본 시트. 절대초 라벨.
    py peek.py <mp4> <out.jpg> <a> <b> <step> [cols=10] [w=180] [cx=0.5]"""
import subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw
mp4, out, a, b, st = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
cols = int(sys.argv[6]) if len(sys.argv) > 6 else 10
cw = int(sys.argv[7]) if len(sys.argv) > 7 else 180
cx = float(sys.argv[8]) if len(sys.argv) > 8 else 0.5
WIN_W, WIN_H = 1080, 1052
tmp = Path(tempfile.mkdtemp())
# 높이 1052 로 키운 뒤 가로 1080 크롭(cx = 크롭 가운데 비율)
vf = f"fps={1/st},scale=-2:{WIN_H},crop={WIN_W}:{WIN_H}:(iw-{WIN_W})*{cx}:0,scale={cw}:-2"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", mp4, "-vf", vf, str(tmp / "%04d.jpg")], check=True)
fr = sorted(tmp.glob("*.jpg"))
w, h = Image.open(fr[0]).size
rows = (len(fr) + cols - 1) // cols
sh = Image.new("RGB", (cols * w, rows * (h + 14)), "white"); d = ImageDraw.Draw(sh)
for i, f in enumerate(fr):
    x, y = i % cols * w, i // cols * (h + 14)
    sh.paste(Image.open(f), (x, y + 14)); d.text((x + 3, y + 1), f"{a + i * st:.1f}", fill=(220, 0, 0)); f.unlink()
sh.save(out, quality=82); tmp.rmdir(); print(out, len(fr))
