# 전후 비교(옛 꺾은선 vs 새 원본선 마스크) — 같은 시각·같은 자리 얼굴·머리 960px 잘라 나란히. py compare.py P1 out.png
import sys, pathlib, io
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont
P, out = sys.argv[1], sys.argv[2]
f = (pathlib.Path(__file__).parent / P / "template" / "index.html").as_uri()
SHOTS = [(1.95, (960 - 240, 395 - 300, 960 + 240, 395 + 180)), (5.2, (1180 - 240, 430 - 280, 1180 + 240, 430 + 200))]   # (초, 얼굴 영역 480x480)
F = ImageFont.truetype("malgun.ttf", 22)
rows = []
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--allow-file-access-from-files"])
    for t, box in SHOTS:
        row = []
        for mode in ("#legacy", ""):
            pg = b.new_page(viewport={"width": 1920, "height": 1080}); pg.goto(f + mode); pg.wait_for_function("window.__S", timeout=15000)
            pg.evaluate(f"window.__S.render({t})"); pg.wait_for_timeout(300)
            im = Image.open(io.BytesIO(pg.screenshot())).crop(box); pg.close()
            d = ImageDraw.Draw(im); d.rectangle([0, 0, 480, 30], fill="white"); d.text((6, 2), ("전: 꺾은선" if mode else "후: 원본선 마스크") + f" t={t}", fill="black", font=F)
            row.append(im)
        rows.append(row)
    b.close()
sh = Image.new("RGB", (960, 480 * len(rows)), "white")
for r, row in enumerate(rows):
    for c, im in enumerate(row): sh.paste(im, (c * 480, r * 480))
sh.save(out); print(out)
