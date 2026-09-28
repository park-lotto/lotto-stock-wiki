"""Vertex 발급 안내 영상 5단계용 — 설정 화면의 '내 구글 Vertex 연결' 카드를 진짜 앱(격리 DB·로그인 끔)으로 캡처한다.
  py tools/vertex_guide/capture_settings.py <출력폴더>
  구글 콘솔 화면과 같은 비율(가로 2000·배율 1.24)로 찍어 영상에서 섞어도 튀지 않게 한다."""
import sys, time, shutil, threading, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / '_work'; shutil.rmtree(work, ignore_errors=True); work.mkdir()
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False
module.keycrypt.enabled = lambda: True   # 캡처용: 카드 보이기만(저장은 안 한다)
PORT = 8797
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)
FAKE = '{\n  "type": "service_account",\n  "project_id": "my-project-123456",\n  "private_key_id": "••••••••",\n  "client_email": "shorts@my-project-123456.iam.gserviceaccount.com"\n}'
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 2000, 'height': 1008}, device_scale_factor=1.24)
    pg.goto(f'http://127.0.0.1:{PORT}/settings.html#keys', wait_until='networkidle'); pg.wait_for_timeout(1500)
    card = pg.locator('#vertexCard')
    if not card.is_visible():
        print('카드가 안 보인다(vertex 비활성?)', pg.evaluate("getComputedStyle(document.getElementById('vertexCard')).display")); sys.exit(1)
    card.scroll_into_view_if_needed(); pg.evaluate("window.scrollBy(0,-120)"); pg.wait_for_timeout(400)
    pg.screenshot(path=str(out / '30_settings_vertex_empty.png'))
    pg.fill('#vertexJson', FAKE); pg.wait_for_timeout(300)
    pg.screenshot(path=str(out / '31_settings_vertex_pasted.png'))
    box = pg.evaluate("(()=>{const r=id=>{const b=document.getElementById(id).getBoundingClientRect();return [b.x,b.y,b.width,b.height].map(v=>Math.round(v*1.24))};return {card:r('vertexCard'),json:r('vertexJson'),btn:r('vertexBtn')}})()")
    print('BOXES', box)
    b.close()
