# -*- coding: utf-8 -*-
"""훅 시선집중 모션 '없음'(관제 262)이 편집기 화면 → 서버 검증 → 진짜 렌더러(render_scene_style.js)까지 정지로 가는지 본다.
   대조군으로 '줌 펀치'도 같이 돌려, 검사가 실제로 움직임을 잡는지(줌 펀치는 확대가 나와야) 확인한다.
   py tools/scene_fx/verify_hook_motion_none.py <출력폴더>     실패하면 rc=1."""
import sys, json, pathlib, subprocess, threading, functools, http.server
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from shopping_shorts import scene_style
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(type('Quiet', (http.server.SimpleHTTPRequestHandler,), {'log_message': lambda *a: None}), directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start(); port = srv.server_address[1]
fails = []
def check(ok, msg): print(("OK  " if ok else "FAIL"), msg); ok or fails.append(msg)
snaps = {}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1800, 'height': 1300}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'http://127.0.0.1:{port}/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    pg.evaluate("document.querySelector('[data-hook-motion]').closest('details').open=true")   # 고객도 접힌 '훅' 묶음을 펼쳐서 누른다
    rect = lambda: pg.eval_on_selector('.scene-media-clip', 'e=>{const r=e.getBoundingClientRect();return [r.width,r.height]}')
    for motion in ('zoom-punch', 'none'):
        pg.click(f'[data-hook-motion="{motion}"]')
        active = pg.eval_on_selector_all('[data-hook-motion].active', 'els=>els.map(e=>e.dataset.hookMotion)')
        pg.evaluate('sceneStyle.motionAt(0)'); w0 = rect()
        pg.evaluate('sceneStyle.motionAt(150)'); w1 = rect()
        cam = [pg.evaluate(f'sceneStyle.cameraAt({t})')['zoom'] for t in (0, 150, 300, 500)]
        snaps[motion] = pg.evaluate('window.sceneStyle.snapshot()')
        print(motion, '눌린 버튼', active, '화면 폭 0ms/150ms', w0, w1, 'cameraAt 배율', cam)
        check(active == [motion], f'{motion}: 그 버튼만 눌림')
        check(snaps[motion].get('hookMotion') == motion, f'{motion}: 저장값 hookMotion={snaps[motion].get("hookMotion")}')
        if motion == 'none':
            check(abs(w1[0] - w0[0]) < .1 and max(cam) == 1, 'none: 화면 확대 없음(편집기)')
            label = pg.evaluate("document.querySelector('[data-hook-motion]').closest('.hook-motion').querySelector('.hook-motion-head small').textContent")
            check('없음' in label, f'none: 안내 글 "{label}"')
        else:
            check(w1[0] > w0[0] * 1.05 and max(cam) > 1.05, '대조군 zoom-punch: 화면 확대 나옴(검사가 움직임을 잡는다)')
    pg.locator('#a-live-preview').screenshot(path=str(out / 'editor_none.png'))
    check(not errs, f'페이지 오류 {errs}'); b.close()
srv.shutdown()
ctx_scenes = [{'start': 0, 'end': 1.5, 'caption': '', 'caption_visible': True, 'beat_idx': 0, 'kind': 'hook'},
              {'start': 1.5, 'end': 3, 'caption': '전 세계 건망증 환자들의', 'caption_visible': True, 'beat_idx': 1, 'kind': 'body'}]
for motion, snap in snaps.items():
    snap = scene_style.validate_snapshot(snap)   # 서버가 저장 전에 돌리는 그 검증(422 원인)
    d = out / motion; d.mkdir(exist_ok=True)
    (d / 'req.json').write_text(json.dumps({'snapshot': snap, 'context': {'jobId': None, 'text': snap['text'], 'scenes': ctx_scenes}, 'output': str(d)}, ensure_ascii=False), encoding='utf-8')
    r = subprocess.run(['node', str(ROOT / 'tools/render_scene_style.js'), str(d / 'req.json')], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, cwd=str(ROOT))
    check(r.returncode == 0, f'{motion}: 렌더러 rc={r.returncode} {r.stderr[-300:]}')
    lf = d / 'scene-style-layers.json'; layers = json.loads(lf.read_text(encoding='utf-8')) if lf.exists() else []
    hook = layers[0] if layers else None
    cam = (hook or {}).get('camera') or []
    anim = (hook or {}).get('animation') or []
    print(motion, '렌더 첫 장면: camera 프레임', len(cam), '최대 배율', max([f.get('zoom', 1) for f in cam] or [1]), '| 움직이는 프레임', len(anim))
    if motion == 'none': check(not cam and not anim, 'none: 렌더 첫 장면 camera·애니 프레임 없음(정지)')
    else: check(max([f.get('zoom', 1) for f in cam] or [1]) > 1.05, '대조군 zoom-punch: 렌더 camera 확대 있음')
print('결과:', 'PASS' if not fails else f'FAIL {len(fails)}건'); sys.exit(1 if fails else 0)
