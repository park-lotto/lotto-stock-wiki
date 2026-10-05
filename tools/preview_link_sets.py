"""구매링크 안내 세트 디자인을 눈으로 보는 견본(관제 133): 숏폼 3종(편집 화면 그대로) + 롱폼 3종(롱폼 화면 그대로).

  py tools/preview_link_sets.py <결과 폴더>
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
    for s in ('time', 'event', 'stock', 'crowd', 'price', 'spot'):
        lf.goto(base + '/out/link-longform-stage.html?' + urllib.parse.urlencode({'src': '/' + plain.relative_to(ROOT).as_posix() if plain.is_relative_to(ROOT) else '', 'set': s, 'where': where, 'channel': '숏템메이커'}))
        if not plain.is_relative_to(ROOT):
            import base64
            uri = 'data:image/png;base64,' + base64.b64encode(plain.read_bytes()).decode()
            lf.evaluate("u=>{for(const id of ['#lf-bg','#lf-fg'])document.querySelector(id).style.backgroundImage=`url(${u})`}", uri)
        lf.evaluate('document.fonts.ready'); lf.wait_for_timeout(400)
        # 움직임 한 바퀴를 시간을 못 박아 찍는다(렌더가 할 방식 그대로) → 견본 mp4
        fr = out / f'_frames_{s}'; fr.mkdir(exist_ok=True); loop = lf.evaluate('linkLongform.loopMs'); n = round(loop / 1000 * 30) * 2   # 4.8초 — 시계가 몇 초 줄어드는 게 보이게
        for f in range(n):
            lf.evaluate('t=>linkLongform.motionAt(t)', f / 30 * 1000); lf.locator('#lf-stage').screenshot(path=str(fr / f'{f:04d}.png'))
            if f == round(n * .2): (out / f'롱폼_{s}.png').write_bytes((fr / f'{f:04d}.png').read_bytes())
        import subprocess
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', str(fr / '%04d.png'), '-pix_fmt', 'yuv420p', '-vf', 'scale=1280:720', str(out / f'롱폼_{s}.mp4')], check=True)
    print('오류', errs); b.close()
srv.shutdown()
