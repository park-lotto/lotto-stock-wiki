import os, sys; sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
from PIL import Image
D = os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h in [("title", 1080, 300), ("gate", 860, None)]:
        pg = b.new_page(viewport={"width": w, "height": h or 1000}, device_scale_factor=2 if name == "gate" else 1)
        pg.goto("file:///" + D.replace("\\", "/") + f"/{name}.html"); pg.wait_for_timeout(800)
        pg.screenshot(path=os.path.join(D, f"out_{name}.png"), full_page=(h is None))
    b.close()
Image.open(os.path.join(D, "bg_icon.png")).convert("RGB").resize((500, 500), Image.LANCZOS).save(os.path.join(D, "out_icon.png"))
for n in ["title", "gate", "icon"]: print(n, Image.open(os.path.join(D, f"out_{n}.png")).size)
