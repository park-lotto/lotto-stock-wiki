# -*- coding: utf-8 -*-
"""세그먼트별 시작·중간·끝 프레임을 한 장에 모아 시각 정합을 눈으로 확인한다."""
import sys, json, os, sqlite3, subprocess
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"C:\Users\CH\Desktop\로또의 주식"
sys.path.insert(0, ROOT); os.chdir(ROOT)
from shopping_shorts.config import DB_PATH
from PIL import Image, ImageDraw

JOB, VID, LO, HI = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
ex = json.loads(sqlite3.connect(DB_PATH).execute(
    "select extract_json from mix_jobs where job_id=?", (JOB,)).fetchone()[0])
segs = ex[VID]["segments"]
vpath = os.path.join(ROOT, "shopping_shorts", "data", "mix_jobs", JOB, VID, VID + ".mp4")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"sheet_{VID}_{LO}-{HI}")
os.makedirs(out, exist_ok=True)
W, H = 320, 180
rows = []
for i in range(LO, HI + 1):
    s = segs[i]; a, b = float(s["start"]), float(s["end"])
    ts = [a + 0.15, (a + b) / 2, max(a, b - 0.15)]
    imgs = []
    for k, t in enumerate(ts):
        f = os.path.join(out, f"s{i}_{k}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", vpath, "-frames:v", "1",
                        "-vf", f"scale={W}:{H}", f], stdin=subprocess.DEVNULL, timeout=60)
        imgs.append(Image.open(f) if os.path.exists(f) else Image.new("RGB", (W, H), "black"))
    rows.append((i, a, b, s.get("scene_desc", ""), imgs))
    print(f"seg{i:>2} {a:6.2f}-{b:6.2f}s | {s.get('scene_desc','')}")
sheet = Image.new("RGB", (W * 3 + 60, H * len(rows)), "white")
d = ImageDraw.Draw(sheet)
for r, (i, a, b, desc, imgs) in enumerate(rows):
    d.text((4, r * H + 4), f"seg{i}", fill="red")
    d.text((4, r * H + 20), f"{a:.1f}", fill="black")
    d.text((4, r * H + 34), f"{b:.1f}", fill="black")
    for k, im in enumerate(imgs):
        sheet.paste(im, (60 + k * W, r * H))
p = os.path.join(out, "sheet.png"); sheet.save(p); print("SHEET", p)
