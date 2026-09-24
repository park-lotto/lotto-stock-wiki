"""'원본 영상 그대로'가 **틀 없는 진짜 템플릿(plain)**으로 도는가 (2026-09-24 사장님
 "오른쪽 문구 텍스트에 헤드카피랑 자막 탭을 넣고, 펼치면 신버전처럼 정돈되게").

왜 이렇게 바꿨나: 종전 원본 모드는 '아무것도 안 그리는 모드'라 스냅샷이 null이었다 →
  신버전 제목·자막 카드가 동작할 자리가 없고, 저장·렌더도 옛 ffmpeg 경로로 갈렸다.
  id 'plain' 템플릿(띠 없음·영상 전체화면·제목/자막 줄만)으로 만들면 **모든 기존 기능이 그대로** 살아난다.

  ① 목록에는 안 보인다(20개 그대로). 왼쪽 '템플릿 없음' 카드가 고른다
  ② 고르면 presetId='plain'이고 **저장 가능한 스냅샷**이 나온다(종전엔 null)
  ③ 오른쪽에 신버전 카드(제목·자막)가 그대로 뜬다
  ④ 훅=제목 두 줄 / 본문=제목+자막, 자막은 화면 아래쪽(75% 아래)에 온다
  ⑤ 진짜 렌더(render_layers)에서 제목·자막이 실제로 찍힌다
"""
import sys, pathlib, threading, functools, http.server, socketserver, shutil
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
PORT = 8802
class Q(socketserver.TCPServer): allow_reuse_address = True
srv = Q(('127.0.0.1', PORT), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
CTX = {"jobId": "pt", "text": {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어",
        "bodyTitle": "주부들도 감탄한 천재 아이디어?"},
       "scenes": [{"start": 0, "end": 2, "caption": "요리할 때마다", "caption_visible": True, "beat_idx": 0, "kind": "hook"},
                  {"start": 2, "end": 4, "caption": "이건 바로 핑거 찹스틱", "caption_visible": True, "beat_idx": 1, "kind": "body"}]}
SPOT = """()=>{const L=document.querySelector('#a-live-preview');const r=L.getBoundingClientRect();const out={};
  for(const e of L.querySelectorAll('.precision-text'))out[e.dataset.editBind]=Math.round((e.getBoundingClientRect().top-r.top)/r.height*100);
  out.카드=[...document.querySelectorAll('.scene-text-panel > .text-group')].filter(e=>e.offsetParent!==null).map(e=>e.querySelector('summary b').textContent);
  return out}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:120]))
    pg.goto(f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html', wait_until='domcontentloaded'); pg.wait_for_timeout(4000)
    pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [CTX]); pg.wait_for_timeout(1000)
    cards = pg.evaluate("()=>document.querySelectorAll('[data-p20]').length")
    need(cards == 20, f'① 목록은 20개 그대로 (실제 {cards}) — plain은 목록에 안 낀다')
    pg.click('[data-none]'); pg.wait_for_timeout(1200)
    snap = pg.evaluate("()=>window.sceneStyle.snapshot()")
    need(bool(snap) and snap.get('presetId') == 'plain', f'② 원본을 고르면 저장 가능한 스냅샷 (presetId {snap and snap.get("presetId")}) — 종전엔 null이라 아무것도 저장 못 했다')
    pg.evaluate("()=>{window.sceneStyle.show(0);return 1}"); pg.wait_for_timeout(700)
    hook = pg.evaluate(SPOT)
    need('제목' in hook['카드'] and '자막' in hook['카드'], f'③ 신버전 카드가 그대로 뜬다 {hook["카드"]}')
    need(hook.get('hook1') is not None and hook['hook1'] < 30, f'④ 훅: 제목이 위쪽에 {hook.get("hook1")}%')
    pg.evaluate("()=>{window.sceneStyle.show(1);return 1}"); pg.wait_for_timeout(700)
    body = pg.evaluate(SPOT)
    need(body.get('bodyTitle') is not None and body['bodyTitle'] < 30, f'④ 본문: 제목 {body.get("bodyTitle")}%')
    # 2026-09-25 사장님: 원본(인스타식) 자막은 **제목 바로 아래 · 박스 없이**. (종전 기준은 화면 아래 81%·검정 박스)
    need(body.get('caption') is not None and 18 <= body['caption'] <= 30,
         f'④ 본문: 자막이 제목 바로 아래 {body.get("caption")}% (종전 81%)')
    BOX = "()=>{const e=document.querySelector('#a-live-preview .precision-patch[data-edit-bind=caption]');if(!e)return null;const c=getComputedStyle(e);return c.backgroundColor+'|'+c.backgroundImage}"
    bx = pg.evaluate(BOX)
    need(bx is not None and bx.startswith('rgba(0, 0, 0, 0)') and bx.endswith('none'), f'④ 본문: 자막 박스 없음(투명) {bx} — 종전 검정 박스')
    # ⑥ 2026-09-24 고객 제보: "썰쇼핑형·전장면 고정형 **둘 다** 원본 영상 그대로를 고르면 자막이 안 보인다.
    #    예전엔 장면마다 자막을 위로 옮겨 상품을 가리지 않게 썼다." → 원본은 훅 장면에도 자막이 나와야 한다.
    pg.evaluate("()=>{window.sceneStyle.show(0);return 1}"); pg.wait_for_timeout(700)
    h2 = pg.evaluate(SPOT)
    need(h2.get('caption') is not None and 18 <= h2['caption'] <= 30 and h2['caption'] > (h2.get('hook2') or 0),
         f"⑥ 썰쇼핑형 원본: **훅 장면에도** 자막이 보인다 ({h2.get('caption')}%) — 고치기 전엔 아예 없었다")
    CAPFIELD = "()=>!!document.querySelector('[data-field-key=\"caption\"]:not([hidden])')"
    need(pg.evaluate(CAPFIELD), '⑥ 자막 칸(문구·위치 옮기기)이 열려 있다')
    pg.evaluate("()=>{document.querySelector('[data-template-mode=\"continuous\"]').click();return 1}"); pg.wait_for_timeout(1200)
    pg.click('[data-none]'); pg.wait_for_timeout(1200)
    cid = pg.evaluate("()=>window.sceneStyle.snapshot()?.presetId")
    need(cid == 'plain', f"⑥ 전장면 고정형에서도 원본 카드가 먹는다 (presetId {cid}) — 고치기 전엔 아무것도 안 그리는 모드로 빠졌다")
    pg.evaluate("()=>{window.sceneStyle.show(1);return 1}"); pg.wait_for_timeout(800)
    c2 = pg.evaluate(SPOT)
    need(c2.get('caption') is not None and 18 <= c2['caption'] <= 30, f"⑥ 전장면 고정형 원본에도 자막이 제목 아래에 보인다 ({c2.get('caption')}%)")
    bx2 = pg.evaluate(BOX)
    need(bx2 is not None and bx2.startswith('rgba(0, 0, 0, 0)'), f'⑥ 전장면 고정형 원본도 박스 없음 {bx2}')
    need(not errs, f'페이지 오류 없음 {errs[:2]}')
    b.close()
srv.shutdown()
# ⑤ 진짜 렌더
from shopping_shorts import scene_style, video_assemble as va
from PIL import Image
out = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'out' / '_plainqa'
shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
timeline = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
             'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}}
            for i, c in enumerate(['주부들도 감탄한 천재 아이디어', '이건 바로 핑거 찹스틱'])]
snap = scene_style.validate_snapshot({'version': 1, 'mode': 'story', 'presetId': 'plain', 'sceneIndex': 0, 'frameKind': 'hook',
    'text': CTX['text']})
scene_style.render_layers(timeline, snap, out / 'layers', {'text': '주부들도 감탄한\n천재 아이디어'}, 'plainqa')
pngs = sorted((out / 'layers').rglob('*.png'))
need(len(pngs) >= 2, f'⑤ 장면별 투명 레이어가 나온다 ({len(pngs)}장)')
def ink(png, a0, a1):
    im = Image.open(png).convert('RGBA'); w, h = im.size; al = im.split()[3]
    return sum(1 for y in range(int(h * a0), int(h * a1), 3) for x in range(int(w * .1), int(w * .9), 6) if al.getpixel((x, y)) > 40)
if len(pngs) >= 2:
    need(ink(pngs[0], .05, .25) > 300, f'⑤ 훅 레이어 위쪽에 제목이 찍힌다 ({ink(pngs[0], .05, .25)}점)')
    need(ink(pngs[1], .19, .30) > 300 and ink(pngs[1], .75, .92) < 30, f'⑤ 본문 레이어: 자막이 제목 아래에 찍히고({ink(pngs[1], .19, .30)}점) 아래쪽은 비었다({ink(pngs[1], .75, .92)}점)')
    im = Image.open(pngs[1]).convert('RGBA'); W, H = im.size
    edge = sum(1 for y in range(int(H * .19), int(H * .30), 3) for x in (int(W * .02), int(W * .98)) if im.getpixel((x, y))[3] > 40)
    need(edge == 0, f'⑤ 렌더 레이어에 자막 박스(가장자리까지 칠한 띠)가 없다 (가장자리 칠 {edge}점)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
