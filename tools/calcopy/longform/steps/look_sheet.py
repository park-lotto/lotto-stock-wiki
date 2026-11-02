# 화면 견본 시트: 모션 변형마다 한 장씩 모은다.
# 사용: 작업 폴더에서 python -X utf8 <경로>/look_sheet.py [결과.jpg]
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio.output import *
tl = direct(json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8")))
got, seen = [], set()
def want(key, t, name):
    if key not in seen: seen.add(key); got.append((t, name))
for s in tl["shots"]:
    end = s["t1"] - 0.3
    for j, b in enumerate(s.get("beats", [])):
        nx = s["beats"][j + 1][0] if j + 1 < len(s["beats"]) else s["t1"] - s["t0"]; want(("stage", b[1]), s["t0"] + (b[0] + nx) / 2, "무대 " + b[1])
    if s["type"] in ("bignum", "bar", "labels", "vs", "quote"): want((s["type"], s.get("look")), end if not s.get("swaps") else s["t0"] + s["swaps"][0][0] - 0.3, f'{s["type"]} {s.get("look")}')
    if s["type"] == "typo": want(("typo", s["modes"][0]), s["t0"] + 0.1, "문장 " + s["modes"][0])
for e in tl["events"]:
    if e["kind"].startswith("bumper"): want(("bumper", e["look"]), e["t"] + e["dur"] * 0.6, "범퍼 " + e["look"])
cols = 5; tw, th = 512, 288; rows = (len(got) + cols - 1) // cols; sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
for i, (t, name) in enumerate(got):
    im = film_grain(make_frame(t, tl), t).resize((tw, th), Image.BILINEAR); ImageDraw.Draw(im).text((200, 4), name, fill=(0, 255, 120), font=face("B", 22))
    sheet.paste(im, (i % cols * tw, i // cols * th))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BUILD, "look_sheet.jpg")
sheet.save(out, quality=88); print("저장:", out, len(got), "장")
