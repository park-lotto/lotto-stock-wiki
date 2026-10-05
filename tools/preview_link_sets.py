"""구매링크 안내 세트 디자인을 눈으로 보는 견본(관제 133): 숏폼 3종(편집 화면 그대로) + 롱폼 3종(롱폼 화면 그대로).

  py tools/preview_link_sets.py <결과 폴더> [comment|desc]
"""
import sys, io, pathlib, threading, functools, http.server, urllib.parse
ROOT = pathlib.Path(__file__).resolve().parents[1]
from PIL import Image
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
where = sys.argv[2] if len(sys.argv) > 2 else 'comment'
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{srv.server_port}'
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={'width': 1500, 'height': 1000}, device_scale_factor=2)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(base + '/out/scene-style-ui-showcase.html'); pg.wait_for_timeout(1500)
    n = pg.evaluate('sceneStyle.sceneCount()'); pg.evaluate(f'sceneStyle.show({n - 1})'); pg.wait_for_timeout(500)
    plain = out / '_쇼츠한장.png'; pg.locator('#a-live-preview').screenshot(path=str(plain))
    shots = []
    for d in pg.evaluate("[...document.querySelectorAll('[data-shopset-design]')].map(b=>b.dataset.shopsetDesign)"):
        pg.evaluate(f"document.querySelector('[data-shopset-design=\"{d}\"]').click();document.querySelector('[data-shopset=\"here\"]').click()"); pg.wait_for_timeout(700)
        r = pg.evaluate("(()=>{const r=document.querySelector('#a-live-preview').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
        shots.append(Image.open(io.BytesIO(pg.screenshot(clip={'x': r[0] - 12, 'y': r[1] - 8, 'width': r[2] + 24, 'height': r[3] * 1.09 + 16}))))
    sheet = Image.new('RGB', (sum(s.width for s in shots), max(s.height for s in shots)), '#0b1418'); x = 0
    for s in shots: sheet.paste(s, (x, 0)); x += s.width
    sheet.save(out / '숏폼_디자인3종.png')
    lf = b.new_page(viewport={'width': 1280, 'height': 720}); lf.on('pageerror', lambda e: errs.append(str(e)))
    for s in ('pin', 'ask', 'bar'):
        lf.goto(base + '/out/link-longform-stage.html?' + urllib.parse.urlencode({'src': '/' + plain.relative_to(ROOT).as_posix() if plain.is_relative_to(ROOT) else '', 'set': s, 'where': where}))
        if not plain.is_relative_to(ROOT):
            import base64
            uri = 'data:image/png;base64,' + base64.b64encode(plain.read_bytes()).decode()
            lf.evaluate("u=>{for(const id of ['#lf-bg','#lf-fg'])document.querySelector(id).style.backgroundImage=`url(${u})`}", uri)
        lf.wait_for_timeout(700); lf.locator('#lf-stage').screenshot(path=str(out / f'롱폼_{s}.png'))
    print('오류', errs); b.close()
srv.shutdown()
