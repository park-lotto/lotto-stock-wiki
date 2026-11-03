# 빠른 확인: index.html 을 크롬으로 열어 몇 초 지점 그림 + 콘솔 오류. py snap.py P1 out.png 1.0 2.5 ...
import sys, pathlib
from playwright.sync_api import sync_playwright
P, out, ts = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3:]]
f = pathlib.Path(__file__).parent / P / "template" / "index.html"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--allow-file-access-from-files"]); pg = b.new_page(viewport={"width": 1920, "height": 1080})
    errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri()); pg.wait_for_function("window.__S", timeout=15000)
    from PIL import Image; import io
    shots = []
    for t in ts:
        pg.evaluate(f"window.__S.render({t})"); pg.wait_for_timeout(150)
        shots.append(Image.open(io.BytesIO(pg.screenshot())).resize((480, 270)))
    sh = Image.new("RGB", (480 * min(4, len(shots)), 270 * ((len(shots) + 3) // 4)), "white")
    for i, s in enumerate(shots): sh.paste(s, ((i % 4) * 480, (i // 4) * 270))
    sh.save(out); print("errors:", errs[:5]); b.close()
