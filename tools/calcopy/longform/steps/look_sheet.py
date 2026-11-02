# 화면 견본 시트: 샷 종류마다 말이 끝나 갈 때의 장면을 한 장으로 모은다.
# 사용: 작업 폴더에서 python -X utf8 <경로>/look_sheet.py [결과.jpg]
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio.output import *
tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
got, seen = [], {}
for s in tl["shots"]:
    key = (s["type"], s["s"][0] % 3 if s["type"] in ("stock", "ai") else 0)
    if seen.get(key, 0) < (2 if s["type"] in ("bar", "bignum", "typo") else 1):
        seen[key] = seen.get(key, 0) + 1; got.append((s["t1"] - 0.4, f'{s["type"]} s{s["s"][0]}'))
for e in tl["events"]:
    if e["kind"] in ("bumper", "outro"): got.append((e["t"] + min(e["dur"] - 0.1, 2.0), e["kind"]))
cols = 4; tw, th = 640, 360; rows = (len(got) + cols - 1) // cols; sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
for i, (t, name) in enumerate(got):
    im = film_grain(make_frame(t, tl), t).resize((tw, th), Image.BILINEAR); ImageDraw.Draw(im).text((8, 8), name, fill=(0, 255, 120), font=face("B", 22))
    sheet.paste(im, (i % cols * tw, i // cols * th))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BUILD, "look_sheet.jpg")
sheet.save(out, quality=88); print("저장:", out, len(got), "장")
