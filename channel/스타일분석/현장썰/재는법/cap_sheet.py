# -*- coding: utf-8 -*-
"""원음 구간 자막 눈 확인용 시트 — 편마다 [나레 구간 1장 | 원음 구간 2장] 프레임을 나란히 (관제 097).
    PYTHONUTF8=1 py channel/스타일분석/현장썰/재는법/cap_sheet.py <out.jpg> id1 id2 ...
시각은 비교표.json 의 받아쓰기(나레 첫 구절 가운데 / 원음 구절 가운데). 판정은 사람이 눈으로 한다(OCR 한도 소진 편 포함).
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import mp4_of, ddir, audio_of  # noqa: E402
HERE = Path(__file__).resolve().parent
rows = {r["id"]: r for r in json.loads((HERE.parent / "비교표.json").read_text(encoding="utf-8"))["rows"]}
out, ids = sys.argv[1], sys.argv[2:]
W = 300
def grab(mp4, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={W}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert("RGB")
font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 16)
tiles = []
for vid in ids:
    r = rows[vid]
    d = json.loads((ddir(vid, r["channel"]) / "뜯기.json").read_text(encoding="utf-8"))
    A, _ = audio_of(vid, r["channel"], d)
    seg = A["segments"]
    narr = [s for s in seg if s.get("lang") == "ko" and s.get("kind") == "narration"]
    src = [s for s in seg if not (s.get("lang") == "ko" and s.get("kind") == "narration")]
    ts = [("나레", (narr[0]["start"] + narr[0]["end"]) / 2)] if narr else []
    for s in (src[:1] + src[-1:] if len(src) > 1 else src):
        ts.append(("원음", (float(s["start"]) + float(s["end"])) / 2))
    ims = [(lab, t, grab(mp4_of(vid, r["channel"]), t)) for lab, t in ts]
    h = max(im.height for _, _, im in ims) + 24
    row = Image.new("RGB", (W * 3, h), "white")
    dr = ImageDraw.Draw(row)
    for i, (lab, t, im) in enumerate(ims[:3]):
        row.paste(im, (i * W, 24)); dr.text((i * W + 4, 2), f"{vid} {lab} {t:.1f}s", fill="black", font=font)
    tiles.append(row)
H = sum(t.height for t in tiles)
sheet = Image.new("RGB", (W * 3, H), "white"); y = 0
for t in tiles:
    sheet.paste(t, (0, y)); y += t.height
sheet.save(out, quality=88); print(out, sheet.size)
