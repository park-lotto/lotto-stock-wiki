"""글자 두께·그림자(2026-09-28 사장님 "장면에서 폰트 두께와 그림자 설정, 제일 심플하게" → 09-29 "−/＋ 조절, 수치 나오게" 0~10) — 편집기부터 완성 영상까지 잰다.
  py tools/scene_font_research/check_text_look.py <출력폴더> [--root <검사할 체크아웃>]

  ① 편집기: [폰트] 탭의 두께·그림자 −/슬라이더/＋/숫자를 조절하면 미리보기 글자의 테두리 폭·그림자가 실제로 바뀐다 / 저장값에 실린다 / 다시 열면 그대로
  ② 렌더·캡컷 레이어(render_layers): 같은 설정에서 두께·그림자만 켠 쪽이 글자 잉크가 늘어난다
  ③ 썸네일 한 장(render_layer_one): 마찬가지
  ④ 최종 합성(compose) mp4 프레임: 두 영상의 글자 영역이 다르다
  --root 로 옛 코드(main 폴더 등)를 주면 ①②③④가 실패해야 한다 — 검사가 진짜로 재는지 확인용.
"""
import sys, pathlib, shutil, threading, functools, http.server, socketserver, json, re
args = sys.argv[1:]
ROOT = pathlib.Path(__file__).resolve().parents[2]
if '--root' in args:
    i = args.index('--root'); ROOT = pathlib.Path(args[i + 1]).resolve(); del args[i:i + 2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble as va
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright
out = pathlib.Path(args[0]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

# ── ① 편집기 ───────────────────────────────────────────────
class Q(socketserver.TCPServer): allow_reuse_address = True
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = Q(('127.0.0.1', 0), functools.partial(H, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{srv.server_address[1]}/out/scene-style-ui-showcase.html'
scenes = [{"start": i * 2, "end": i * 2 + 2, "caption": f"{i}번 자막입니다", "caption_visible": True, "beat_idx": i,
           "kind": "hook" if i == 0 else "body"} for i in range(3)]
TEXT = {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어", "bodyTitle": "작은 보조 제목"}
CTX = {"jobId": "tl", "text": TEXT, "scenes": scenes}
STYLE_JS = """()=>{const L=document.querySelector('#a-live-preview');const r={};
  const read=b=>{const e=L.querySelector(`.precision-text[data-edit-bind="${b}"]`);if(e){const s=getComputedStyle(e);r[b]={stroke:parseFloat(s.webkitTextStrokeWidth)||0,shadow:s.textShadow,font:parseFloat(s.fontSize)||0,group:e.dataset.lookGroup}}};
  window.sceneStyle.show(0);['channel','hook1','hook2','bodyTitle'].forEach(read);window.sceneStyle.show(1);read('caption');window.sceneStyle.show(0);return r}"""
LOOKS = {"channel": (20, 25), "titleLarge": (90, 100), "titleSmall": (55, 65), "caption": (35, 45)}
BIND_GROUP = {"channel": "channel", "hook1": "titleLarge", "bodyTitle": "titleSmall", "caption": "caption"}
base_snap = styled_snap = None
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.goto(URL, wait_until='networkidle'); pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [CTX]); pg.wait_for_timeout(700)
    pg.click('[data-left-tab="scene"]'); pg.click('[data-p20="0"]'); pg.wait_for_timeout(500)
    before = pg.evaluate(STYLE_JS); base_snap = pg.evaluate('()=>window.sceneStyle.snapshot()')
    pg.click('[data-left-tab="font"]'); pg.wait_for_timeout(200)
    has_ui = all(pg.locator(f'[data-look-{kind}="{key}"]').count() == 1 for key in ('tw', 'ts') for kind in ('range', 'value')) and pg.locator('[data-look-step]').count() == 4 and pg.locator('[data-look-target]').count() == 4
    need(has_ui, '① 채널명/큰 제목/작은 제목/자막 선택과 두께·그림자 -/슬라이더/+/숫자가 있다')
    if has_ui:
        for target, (weight, shadow) in LOOKS.items():
            pg.click(f'[data-look-target="{target}"]')
            pg.locator('[data-look-range="tw"]').fill(str(weight))
            pg.locator('[data-look-range="ts"]').fill(str(shadow))
        pg.wait_for_timeout(300)
        need(pg.locator('[data-look-value="tw"]').text_content() == '35' and pg.locator('[data-look-value="ts"]').text_content() == '45',
             '① 대상을 바꾸면 그 대상 수치가 독립적으로 보인다')
    after = pg.evaluate(STYLE_JS); styled_snap = pg.evaluate('()=>window.sceneStyle.snapshot()')
    pg.screenshot(path=str(out / 'editor_styled.png'))
    for bind in BIND_GROUP:
        a, z = before.get(bind, {}), after.get(bind, {})
        need(z.get('stroke', 0) > a.get('stroke', 0), f"① {bind} 글자 두께가 커진다 (테두리 {a.get('stroke')}px → {z.get('stroke')}px)")
        need(z.get('shadow') not in (None, 'none') and z.get('shadow') != a.get('shadow'), f"① {bind} 그림자가 생긴다 ({a.get('shadow')} → {z.get('shadow')})")
        need(z.get('group') == BIND_GROUP[bind], f"① {bind}는 {BIND_GROUP[bind]} 조절만 받는다 ({z.get('group')})")
    need(styled_snap.get('textWeight') == {k:v[0] for k,v in LOOKS.items()} and styled_snap.get('textShadow') == {k:v[1] for k,v in LOOKS.items()},
         f"① 저장값에 실린다 (textWeight={styled_snap.get('textWeight')}, textShadow={styled_snap.get('textShadow')})")
    sh = after['hook1']['shadow']; shadow_x = float(re.search(r'\)\s+([\d.]+)px', sh).group(1))
    need(sh.count('rgb(') == 3 and abs(shadow_x - after['hook1']['font'] * .10) < .15,
         f"① 그림자가 썸네일처럼 3회·가로 10%로 그려진다 ({sh})")
    need('textWeight' not in base_snap and 'textShadow' not in base_snap, '① 안 건드린 저장값엔 키가 없다(옛 저장본과 같아 완성본 무효화 없음)')
    # 다시 열기
    pg.goto(URL, wait_until='networkidle'); pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)', [CTX, styled_snap]); pg.wait_for_timeout(700)
    again = pg.evaluate(STYLE_JS)
    need(again.get('hook1', {}).get('stroke') == after.get('hook1', {}).get('stroke'), f"① 다시 열어도 두께 그대로 ({again.get('hook1', {}).get('stroke')}px)")
    pg.click('[data-left-tab="font"]'); pg.wait_for_timeout(200)
    restored = {}
    for target in LOOKS:
        pg.click(f'[data-look-target="{target}"]')
        restored[target] = pg.evaluate("()=>['tw','ts'].map(k=>document.querySelector(`[data-look-range=\"${k}\"]`)?.value)")
    need(restored == {k:[str(v[0]),str(v[1])] for k,v in LOOKS.items()}, f'① 다시 열면 대상별 슬라이더·숫자가 그대로다 {restored}')
    if has_ui:
        for target in LOOKS:
            pg.click(f'[data-look-target="{target}"]')
            pg.locator('[data-look-range="tw"]').fill('0'); pg.locator('[data-look-range="ts"]').fill('0')
        pg.wait_for_timeout(300)
        back = pg.evaluate('()=>window.sceneStyle.snapshot()')
        need('textWeight' not in back and 'textShadow' not in back, '① 기본·없음으로 되돌리면 저장값에서 빠진다')
        legacy = {**base_snap, 'textWeight': 'heavy', 'textShadow': 'soft'}
        pg.goto(URL, wait_until='networkidle'); pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)', [CTX, legacy]); pg.wait_for_timeout(500)
        pg.click('[data-left-tab="font"]')
        old = {}
        for target in LOOKS:
            pg.click(f'[data-look-target="{target}"]')
            old[target] = pg.evaluate("()=>['tw','ts'].map(k=>document.querySelector(`[data-look-range=\"${k}\"]`)?.value)")
        need(all(v == ['100', '50'] for v in old.values()), f'① 옛 전체 저장값은 네 대상 모두 100·50으로 열린다 {old}')
    b.close()
srv.shutdown()

# ── ②③④ 렌더 경로 — 같은 편집기 저장값에서 두께·그림자만 다르게 ─────────────
tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
src = out / 'src.mp4'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=0x3060a0:s=1080x1920:d=2', '-r', '30', '-pix_fmt', 'yuv420p', str(src)])
timeline = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
             'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}}
            for i, c in enumerate(['주부들도 감탄한 천재 아이디어', '이건 바로 핑거 찹스틱'])]
HEAD = {'text': '주부들도 감탄한\n천재 아이디어'}
base = {k: v for k, v in base_snap.items() if k not in ('textWeight', 'textShadow')}
styled = {**base, 'textWeight': {k:v[0] for k,v in LOOKS.items()}, 'textShadow': {k:v[1] for k,v in LOOKS.items()}}
def changed(p1, p2):   # 두 그림에서 눈에 띄게 달라진 점 수(RGBA 합성 후 밝기 차) — 불투명 띠 위 글자도 잡는다
    bg = Image.new('RGBA', Image.open(p1).size, (48, 96, 160, 255))
    g = lambda p: Image.alpha_composite(bg, Image.open(p).convert('RGBA')).convert('L')
    return sum(1 for v in ImageChops.difference(g(p1), g(p2)).getdata() if v > 40)
L = {}
for name, snap in (('base', base), ('styled', styled)):
    scene_style.render_layers(timeline, snap, out / f'layers_{name}', HEAD, 'tlqa')
    L[name] = sorted((out / f'layers_{name}').rglob('*.png'))
for i in range(min(len(L['base']), len(L['styled']))):
    n = changed(L['base'][i], L['styled'][i])
    need(n > 2000, f'② 렌더·캡컷 레이어 {i}번: 글자 부분이 달라진다 (달라진 점 {n})')
one = {n: pathlib.Path(scene_style.render_layer_one(timeline, s, out / f'thumb_{n}', 0, HEAD, 'tlqa')) for n, s in (('base', base), ('styled', styled))}
n = changed(one['base'], one['styled'])
need(n > 2000, f'③ 썸네일 한 장도 글자 부분이 달라진다 (달라진 점 {n})')
frames = {}
for n, s in (('base', base), ('styled', styled)):
    final = out / f'final_{n}.mp4'
    scene_style.compose(str(src), timeline, s, str(final), out / f'cw_{n}', HEAD)
    frames[n] = out / f'frame_{n}.png'
    va._run_ffmpeg(['ffmpeg', '-y', '-ss', '0.5', '-i', str(final), '-frames:v', '1', str(frames[n])])
diff = ImageChops.difference(Image.open(frames['base']).convert('L'), Image.open(frames['styled']).convert('L'))
nf = sum(1 for v in diff.getdata() if v > 40)
need(nf > 2000, f'④ 완성 영상 프레임에서 글자 부분이 달라진다 (달라진 점 {nf})')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
