# -*- coding: utf-8 -*-
"""후보 컷 확인 시트: 줄마다 (이름, 파일, a, b, crop[x,y,w,h]) → 시작·가운데·끝 프레임(크롭 그대로, 9:16 썸네일).  py cand_grid.py out.jpg cands.json"""
import io, json, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
out, cands = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 16)
TW, TH = 180, 320
sheet = Image.new("RGB", (4 * (3 * TW + 20), ((len(cands) + 3) // 4) * (TH + 30)), "black")
d = ImageDraw.Draw(sheet)
for k, (name, f, a, b, cr) in enumerate(cands):
    x0, y0 = (k % 4) * (3 * TW + 20), (k // 4) * (TH + 30)
    d.text((x0 + 4, y0 + 4), f"{name} {a}-{b}", fill="yellow", font=font)
    for j, t in enumerate((a + 0.05, (a + b) / 2, b - 0.05)):
        p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", f, "-frames:v", "1", "-vf",
                            f"crop={cr[2]}:{cr[3]}:{cr[0]}:{cr[1]},scale={TW}:{TH}", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        if p:
            sheet.paste(Image.open(io.BytesIO(p)).convert("RGB"), (x0 + j * TW, y0 + 26))
sheet.save(out, quality=82)
