"""유튜브 화면 자리 겹쳐보기 + 쇼핑 안내 세트(구매링크 칸) 점검 (관제 133, 2026-10-06).

사장님: "장면꾸미기 화면에서는 자리를 표시해 주고 실제 렌더에는 반영이 안 되게 — 있으면 유튜브에 올렸을 때 중복".

  py tools/check_yt_ui.py <결과 폴더>

  ① 편집 화면: 버튼을 누르면 채널명·제목·링크 칸·버튼 자리가 YT_SHORTS_UI 표 그대로 보이고, 다시 누르면 사라진다
  ② 세트(구매링크 칸): 넣기 전/후 화면 차이로 화살표가 실제로 닿는 가장 아래 줄을 잰다 — 채널명 줄 위, 링크 칸 가로 범위 안
  ③ 렌더 조건(?qa=1): 켜 둔 브라우저(localStorage=1)여도 겹쳐보기 층이 아예 없다
  ④ 진짜 렌더 길: render_layers(렌더·캡컷) · render_layer_one(썸네일) · compose(완성 mp4)에 겹쳐보기 색(노랑·하늘 점선)이 0픽셀이고
     세트 화살표는 채널명 줄 위에서 끝난다
"""
import sys, io, pathlib, shutil, threading, functools, http.server
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{srv.server_port}/out/scene-style-ui-showcase.html'

RECTS = """()=>{const p=document.querySelector('#a-live-preview').getBoundingClientRect(),o={};
  const L=document.querySelector('.scene-yt-ui');if(!L)return null;if(getComputedStyle(L).display==='none')return {};
  for(const el of L.children){const r=el.getBoundingClientRect();o[el.dataset.ytUi]=[(r.left-p.left)/p.width*100,(r.top-p.top)/p.height*100,r.width/p.width*100,r.height/p.height*100]}return o}"""
masks_link = None
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 1500, 'height': 1000}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(1500)
    table = pg.evaluate("""()=>{const s=[...document.scripts].find(x=>/scene-style-decorations/.test(x.src));return fetch(s.src).then(r=>r.text()).then(t=>{const m=t.match(/const YT_SHORTS_UI=(\\{[\\s\\S]*?\\n \\});/);return Function('return '+m[1])()})}""")
    CLICK = "document.querySelector('[data-yt-ui-toggle]').click()"
    def off():
        for _ in range(3):
            if pg.evaluate(RECTS) == {}: return
            pg.evaluate(CLICK); pg.wait_for_timeout(200)
    # ⓪ 스위치가 꺼진 계정(기본): 버튼·디자인 고르기가 안 보이고, 세트는 예전 자리·예전 문구 그대로
    need(pg.evaluate("document.querySelector('[data-yt-ui-toggle]').hidden && document.querySelector('[data-shopset-designs]').hidden && document.querySelector('.dec-shopset-target').hidden"), '⓪ 스위치 끔: 자리 버튼·가리킬 곳·디자인 고르기가 숨어 있다')
    pg.evaluate("document.querySelector('[data-shopset=\"here\"]').click()"); pg.wait_for_timeout(200)
    old = pg.evaluate('sceneStyle.effect().masks')
    need([(m.get('graphic') or m.get('text'), m['l'], m['t']) for m in old] == [('arrow_bold', 1, 43), ('영상 속 제품 클릭!', 3, 79)] and pg.evaluate(RECTS) == {}, f"⓪ 스위치 끔: 세트 = 예전 그대로 {[(m.get('graphic') or m.get('text'), m['l'], m['t']) for m in old]}, 자리 표시 안 켜짐")
    pg.evaluate("document.querySelector('[data-shopset=\"clear\"]').click()")
    need(pg.evaluate('sceneDecorations.linkGuide(true)') is True and not pg.evaluate("document.querySelector('[data-yt-ui-toggle]').hidden"), '⓪ 스위치 켬: 자리 버튼이 보인다')
    # ① 겹쳐보기 — 누를 때마다 기본 → 댓글창 화면 → 끔
    need(pg.locator('[data-yt-ui-toggle]').count() == 1, '① 「유튜브 화면 자리」 버튼이 있다')
    need(pg.evaluate(RECTS) == {}, '① 처음에는 꺼져 있다(자리 표시 0개)')
    for mode, name in (('basic', '기본'), ('comment', '댓글창')):
        pg.evaluate(CLICK); pg.wait_for_timeout(300)
        got = pg.evaluate(RECTS) or {}
        need(set(got) == set(table[mode]), f'① [{name}] 자리 {len(got)}개 = 표 {len(table[mode])}개')
        for key, a in table[mode].items():
            g = got.get(key); ok = bool(g) and all(abs(g[i] - a[k]) < .6 for i, k in enumerate('ltwh'))
            need(ok, f"① [{name}] {a['label']}: 표 l{a['l']} t{a['t']} w{a['w']} h{a['h']} / 화면 {[round(x, 1) for x in g] if g else '없음'}")
        r = pg.evaluate("(()=>{const r=document.querySelector('#a-live-preview').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
        pg.screenshot(path=str(out / f'1_자리표시_{name}.png'), clip={'x': r[0] - 20, 'y': r[1] - 10, 'width': r[2] + 40, 'height': r[3] * 1.1 + 20})
    need(table['basic']['link']['t'] > 100 and table['comment']['link']['t'] < 100, '① 링크 칸: 기본 화면은 영상 아래 바깥, 댓글창 화면은 영상 안')
    pg.evaluate(CLICK); pg.wait_for_timeout(200)
    need(pg.evaluate(RECTS) == {}, '① 세 번째 누르면 사라진다')
    # ② 세트 — 넣기 전/후 미리보기 차이(겹쳐보기는 미리보기 밖이라 안 찍힌다)
    pg.evaluate("document.querySelector('[data-shopset-target]').value='link'")
    n = pg.evaluate('sceneStyle.sceneCount()'); pg.evaluate(f'sceneStyle.show({n - 1})'); pg.wait_for_timeout(600)
    shot = lambda: Image.open(io.BytesIO(pg.locator('#a-live-preview').screenshot())).convert('RGB')
    before = shot()
    pg.evaluate("document.querySelector('[data-shopset=\"here\"]').click()"); pg.wait_for_timeout(300)
    need(pg.evaluate(RECTS) != {}, '② 세트를 넣으면 자리 표시가 같이 켜진다')
    masks_link = pg.evaluate('sceneStyle.effect().masks')
    need([m.get('kind') for m in masks_link] == ['graphic', 'badge'], f"② 세트 = 화살표 + 배지 ({[m.get('text') or m.get('graphic') for m in masks_link]})")
    off()   # 자리 표시는 미리보기 위에 겹치므로 재는 동안은 끈다
    W, H = before.size; low = 0; xs = []
    for _ in range(14):                                   # 가리키기 한 바퀴(1.2초)를 넘게 훑는다
        d = ImageChops.difference(before, shot()).point(lambda v: 255 if v > 40 else 0).convert('L')
        y0 = int(H * .78); box = d.crop((0, y0, W // 2, H)).getbbox()        # 배지(위 70~76%) 아래 = 화살표만
        if box: low = max(low, y0 + box[3]); xs.append((box[0], box[2]))
        pg.wait_for_timeout(100)
    tip = low / H * 100; cx = sum((a + c) / 2 for a, c in xs) / max(1, len(xs)) / W * 100
    ch = min((v['channel'] for v in table.values()), key=lambda c: c['t']); lk = table['basic']['link']   # 두 화면 중 더 높은 채널명 줄
    LOW = 97        # 사장님(2026-10-06): 가리키는 것은 실제 링크 칸까지 최대한 내린다 → 영상 맨 아래 3% 안에서 끝나야 한다
    need(LOW <= tip <= 100, f"② 화살표가 닿는 가장 아래 {tip:.1f}% — 영상 맨 아래({LOW}~100%)까지 내려온다")
    def badge_ok(ms): return all(m['t'] + m['h'] <= ch['t'] for m in ms if m.get('kind') == 'badge')
    need(badge_ok(masks_link), f"② 글자 배지는 채널명 줄({ch['t']}%) 위 ({[round(m['t'] + m['h'], 1) for m in masks_link if m.get('kind') == 'badge']})")
    need(lk['l'] <= cx <= lk['l'] + lk['w'], f"② 화살표 가로 가운데 {cx:.1f}% — 링크 칸 가로 범위({lk['l']}~{lk['l'] + lk['w']:.1f}%) 안")
    # ②-2 나머지 디자인도 두 화면의 채널명 줄 위에서 끝나는가(둥실·가리키기 한 바퀴를 훑는다)
    for d, name in (('finger', '손가락 콕'), ('ticket', '링크 티켓')):
        pg.evaluate(f"document.querySelector('[data-shopset-design=\"{d}\"]').click();document.querySelector('[data-shopset=\"here\"]').click()"); pg.wait_for_timeout(300); off()
        low = 0
        for _ in range(14):
            box = ImageChops.difference(before, shot()).point(lambda v: 255 if v > 40 else 0).convert('L').crop((0, H // 2, W // 2, H)).getbbox()
            if box: low = max(low, H // 2 + box[3])
            pg.wait_for_timeout(100)
        ms = pg.evaluate('sceneStyle.effect().masks')
        need(LOW <= low / H * 100 <= 100 and badge_ok(ms), f"② [{name}] 가리키는 끝 {low / H * 100:.1f}% (맨 아래까지) · 글자 배지 아래 {[round(m['t'] + m['h'], 1) for m in ms if m.get('kind') == 'badge']} (채널명 줄 {ch['t']}% 위)")
    pg.evaluate("document.querySelector('[data-shopset-design=\"arrow\"]').click();document.querySelector('[data-shopset=\"here\"]').click()"); pg.wait_for_timeout(300); off()
    masks_link = pg.evaluate('sceneStyle.effect().masks')
    pg.evaluate(CLICK); pg.wait_for_timeout(300); pg.evaluate(CLICK); pg.wait_for_timeout(300)   # 댓글창 화면으로
    r = pg.evaluate("(()=>{const r=document.querySelector('#a-live-preview').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
    pg.screenshot(path=str(out / '2_세트_구매링크칸.png'), clip={'x': r[0] - 20, 'y': r[1] - 10, 'width': r[2] + 40, 'height': r[3] * 1.1 + 20})
    need(not errs, f'페이지 오류 {errs}')
    # ③ 렌더 조건: 켜 둔 브라우저 + ?qa=1
    ctx = b.new_context(); ctx.add_init_script("try{localStorage.setItem('scene_style_yt_ui','1')}catch(e){}")
    p2 = ctx.new_page(); p2.goto(URL); p2.wait_for_timeout(1200)
    p2.evaluate('sceneDecorations.linkGuide(true)')
    need(bool(p2.evaluate(RECTS)), '③ (대조) 켜 둔 브라우저의 편집 화면에는 자리 표시가 있다 — 이 검사가 실제로 잡는다')
    p3 = ctx.new_page(); p3.goto(URL + '?qa=1'); p3.wait_for_timeout(1200)
    need(p3.evaluate("document.querySelectorAll('.scene-yt-ui,[data-yt-ui-toggle]').length") == 0, '③ 렌더 조건(?qa=1)에서는 자리 표시 층·버튼이 아예 없다')
    b.close()
srv.shutdown()

# ④ 진짜 렌더 길
from shopping_shorts import scene_style, video_assemble as va
tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
src = out / 'src.mp4'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1080x1920:d=2', '-r', '30', '-pix_fmt', 'yuv420p', str(src)])
timeline = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
             'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}}
            for i, c in enumerate(['주부들도 감탄한 천재 아이디어', '이건 바로 핑거 찹스틱'])]
TEXT = {'channel': '숏템메이커', 'hook1': '주부들도 감탄한', 'hook2': '천재 아이디어', 'bodyTitle': '주부들도 감탄한 천재 아이디어?'}
effect = {'masks': masks_link}
raw = {'version': 1, 'mode': 'story', 'plainCaption': 2, 'presetId': 'plain', 'sceneIndex': 0, 'frameKind': 'hook', 'text': TEXT,
       'effects': {'0': effect, '1': effect}}
snap = scene_style.validate_snapshot(raw)
kept = [fx.get('masks') for fx in (snap.get('effects') or {}).values()] if isinstance(snap.get('effects'), dict) else []
need(any(kept), f'④ 서버 검증 뒤에도 세트가 스냅샷에 남는다 (effects 키: {list((snap.get("effects") or {}).keys()) if isinstance(snap.get("effects"), dict) else type(snap.get("effects")).__name__})')

def overlay_px(im):
    """겹쳐보기 색(노랑 #FFE600 · 하늘 #7FE7FF 점선) 점 수."""
    im = im.convert('RGBA'); n = 0
    for r, g, bl, a in list(im.getdata()):
        if a > 40 and ((r > 235 and g > 210 and bl < 60) or (110 < r < 150 and g > 215 and bl > 240)): n += 1
    return n
def red_low(im, alpha=True):
    """화살표 빨강(#FF3B30 계열)이 닿는 가장 아래 줄(%)과 그 아래 채널명 줄 밑의 빨강 점 수."""
    im = im.convert('RGBA'); w, h = im.size; px = im.load(); low = 0
    for y in range(0, h, 2):
        for x in range(0, w // 2, 3):
            r, g, bl, a = px[x, y]
            if (a > 120 or not alpha) and r > 200 and g < 110 and bl < 110: low = y; break
    return low / h * 100

scene_style.render_layers(timeline, snap, out / 'layers', {'text': '주부들도 감탄한\n천재 아이디어'}, 'ytqa')
pngs = sorted((out / 'layers').rglob('*.png'))
need(len(pngs) >= 2, f'④ 렌더·캡컷용 레이어 {len(pngs)}장')
worst = 0; tips = []
for p in pngs:
    im = Image.open(p); worst = max(worst, overlay_px(im)); tips.append(red_low(im))
need(worst == 0, f'④ 렌더·캡컷 레이어 {len(pngs)}장에 겹쳐보기 색 {worst}픽셀')
need(pngs and 97 <= max(tips) <= 100, f"④ 레이어에서 화살표가 닿는 가장 아래 {max(tips) if tips else 0:.1f}% (영상 맨 아래 97~100%)")
one = pathlib.Path(scene_style.render_layer_one(timeline, snap, out / 'thumb_style', 1, {'text': '주부들도 감탄한' + chr(10) + '천재 아이디어'}, 'ytqa'))
need(one.exists() and overlay_px(Image.open(one)) == 0 and 95 <= red_low(Image.open(one)) <= 100,
     f'④ 썸네일용 한 장: 겹쳐보기 색 {overlay_px(Image.open(one)) if one.exists() else "없음"}픽셀 · 화살표 {red_low(Image.open(one)) if one.exists() else 0:.1f}%')
final = out / 'final.mp4'
scene_style.compose(str(src), timeline, snap, str(final), out / 'cw', {'text': '주부들도 감탄한\n천재 아이디어'})
need(final.exists() and final.stat().st_size > 1000, '④ 완성 mp4 생성')
if final.exists():
    frame = out / '4_완성본_프레임.png'; va._run_ffmpeg(['ffmpeg', '-y', '-ss', '1.5', '-i', str(final), '-frames:v', '1', str(frame)])
    im = Image.open(frame)
    need(overlay_px(im) == 0, f'④ 완성 영상 프레임에 겹쳐보기 색 {overlay_px(im)}픽셀')
    t = red_low(im, alpha=False); need(97 <= t <= 100, f"④ 완성 영상에서 화살표가 닿는 가장 아래 {t:.1f}%")
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
