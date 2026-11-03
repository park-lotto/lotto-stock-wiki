import subprocess, sys
from PIL import Image, ImageDraw, ImageFont
import build as B, build2 as B2
W = B.W
v = W / "yt4_draft_v3.mp4"
pts = [("open", t) for t in (2.5, 9.0, 16.0, 19.5)]
t = B.dur(W / "seg" / "open.av.mp4")
for sid in B2.BEATS:
    bt, D = B2.beat_times(sid)
    for i, (a, b, x) in enumerate(bt):
        pts.append((f"{sid}-{i + 1}", t + (a + b) / 2))
    t += B.dur(W / "seg" / f"{sid}.v2.mp4")
ims = []
for name, tt in pts:
    p = W / "sh" / f"{name}.jpg"; p.parent.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{tt:.2f}", "-i", str(v), "-frames:v", "1", "-vf", "scale=320:-2", str(p)])
    im = Image.open(p); ImageDraw.Draw(im).text((6, 4), name, fill=(255, 0, 0), font=ImageFont.truetype(B.SUBF, 22)); ims.append(im)
cols = 10
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
s = Image.new("RGB", (w * cols, h * rows), "white")
for k, im in enumerate(ims):
    s.paste(im, ((k % cols) * w, (k // cols) * h))
s.save(W / "sheet_v3.jpg", quality=85)
print(len(ims), "장")
