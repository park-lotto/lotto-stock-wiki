# -*- coding: utf-8 -*-
"""소스 접촉 시트: 클립마다 STEP초 간격 프레임(가로 W) + 시각 라벨.  py sheets.py <out_dir> <step> <mp4...>"""
import io, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out, step, files = Path(sys.argv[1]), float(sys.argv[2]), sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 18)
for f in files:
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)
    ts = [round(i * step, 2) for i in range(int(d / step) + 1) if i * step < d - 0.05]
    ims = []
    for t in ts:
        p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", f, "-frames:v", "1", "-vf", "scale=-2:240", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        if p:
            ims.append((t, Image.open(io.BytesIO(p)).convert("RGB")))
    w = ims[0][1].width; per = max(1, 1600 // w)
    rows = (len(ims) + per - 1) // per
    s = Image.new("RGB", (per * w, rows * 240), "black")
    dr = ImageDraw.Draw(s)
    for k, (t, im) in enumerate(ims):
        x, y = (k % per) * w, (k // per) * 240
        s.paste(im, (x, y)); dr.text((x + 4, y + 2), f"{t:.1f}", fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill="black")
    s.save(out / (Path(f).stem + ".jpg"), quality=80)
    print(Path(f).stem, round(d, 2), len(ims))
