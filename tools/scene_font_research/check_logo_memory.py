"""로고 자동 최종기억(관제 131, 2026-10-05 사장님) — 고객과 같은 꼴(제작소 안 iframe)로 진짜 편집기를 열어 잰다.
  py tools/scene_font_research/check_logo_memory.py <출력폴더>
  ① 기억이 없으면 새 작업에 로고가 없다
  ② 로고를 얹고 크기를 바꾸면 저장 버튼 없이 기억된다(마지막에 손댄 값)
  ③ 새 작업(저장본 없음)을 열면 그 로고가 전 장면에 같은 자리·크기로 있다 — 고치기 전엔 0장면
  ④ 저장본이 있는 작업은 건드리지 않는다(로고 없는 저장본 = 로고 없음)
  ⑤ 한 장면에서만 지우면 기억은 남고, 어느 장면에도 안 남게 지우면 잊는다 → 다음 새 작업에 로고 없음
  ⑥ 내 프리셋 등록에 로고가 담기고, 적용하면 전 장면에 얹힌다 — 고치기 전엔 0장면
  ⑦ 로고가 실제로 그려진다(맨 위 층에 그림 요소, 깨지지 않음)
  ⑧ 자동으로 들어간 로고가 결과물까지 간다(0순위-A1a): 새 작업의 스냅샷 그대로 서버 검증 → 렌더·캡컷 레이어(render_layers)
     → 썸네일 한 장(render_layer_one) → 최종 합성(compose) mp4 프레임. 로고 없는 같은 스냅샷과 로고 자리의 분홍 점 수를 대조한다.
로고 목록 API만 가짜로 준다(정적 서버엔 API가 없다). 그림 파일은 진짜로 out/장면꾸미기_로고/ 아래에 만들었다 지운다. 올리기는 라이브에서 잰다.
"""
import sys, io, json, shutil, pathlib, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
PORT = 8774
class Q(socketserver.TCPServer): allow_reuse_address = True
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = Q(('127.0.0.1', PORT), functools.partial(H, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
HOST = f'http://127.0.0.1:{PORT}/out/'
EDITOR = f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html'
CID_DIR = ROOT / 'out' / '장면꾸미기_로고' / '999999131'      # 검사 전용 계정 폴더(끝나면 지운다)
SRC = '장면꾸미기_로고/999999131/0123456789abcdef.png'
CID_DIR.mkdir(parents=True, exist_ok=True); Image.new('RGBA', (200, 200), (255, 0, 200, 255)).save(ROOT / 'out' / SRC, 'PNG')
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
def ctx(job, n):
    return {"jobId": job, "text": {"channel": "숏템메이커", "hook1": "이케아도 놀랄", "hook2": "한국 천재 발명품", "bodyTitle": "이케아도 놀랄 한국 천재 발명품"},
            "scenes": [{"start": i*2, "end": i*2+2, "caption": f"{i}번 자막", "caption_visible": True, "beat_idx": i, "kind": "hook" if i == 0 else "body"} for i in range(n)]}
LOGOS = "()=>{const o={};for(let i=0;i<sceneStyle.sceneCount();i++){const m=(sceneStyle.effectAt(i).masks||[]).filter(x=>x.kind==='image');if(m.length)o[i]=m.map(x=>[x.src,Math.round(x.l),Math.round(x.t),Math.round(x.w)])}return o}"
MEM = "()=>JSON.parse(localStorage.getItem('scene_style_logo')||'null')"
with sync_playwright() as p:
    b = p.chromium.launch(); bc = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = bc.new_page()
    pg.on('dialog', lambda d: d.accept('로고 프리셋') if d.type == 'prompt' else d.accept())
    pg.route('**/api/produce/scene-style/logo', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({"ok": True, "items": [{"src": SRC}]})))
    def open_job(job, n, snapshot=None):
        """제작소가 하는 그대로: iframe 으로 편집기를 열고 scene-style-context 를 보낸다."""
        pg.goto(HOST, wait_until='domcontentloaded')
        pg.evaluate("(u)=>{const f=document.createElement('iframe');f.id='ed';f.src=u;f.style.cssText='width:1480px;height:980px;border:0';document.body.replaceChildren(f)}", EDITOR)
        fr = pg.frame_locator('#ed'); f = None
        for _ in range(100):
            f = next((x for x in pg.frames if x.url.startswith(EDITOR)), None)
            if f and f.evaluate("()=>!!(window.sceneStyle&&window.sceneDecorations)"): break
            pg.wait_for_timeout(100)
        pg.wait_for_timeout(300)
        pg.evaluate("([c,s])=>document.getElementById('ed').contentWindow.postMessage({type:'scene-style-context',context:c,snapshot:s},location.origin)", [ctx(job, n), snapshot])
        f.wait_for_function("(n)=>window.sceneStyle.sceneCount()===n&&!!window.sceneStyle.context()", arg=n, timeout=8000); pg.wait_for_timeout(400)
        return f
    # ① 기억 없음
    f = open_job('logo-a', 5)
    need(f.evaluate(LOGOS) == {} and f.evaluate(MEM) is None, '① 기억이 없으면 새 작업에 로고가 없다')
    # ② 로고 얹기(내 로고 목록의 버튼 = 고객이 누르는 것) → 크기 바꾸기 → 저장 버튼 없이 기억
    f.wait_for_selector('.dec-my-logo', state='attached', timeout=5000)
    f.evaluate("()=>document.querySelector('.dec-my-logo').click()"); pg.wait_for_timeout(300)
    first = f.evaluate(MEM)
    need(bool(first) and first.get('src') == SRC, f"② 로고를 얹는 순간 기억된다 ({first and [first.get('src'), first.get('l'), first.get('t'), first.get('w')]})")
    f.evaluate("()=>{const r=document.querySelector('[data-dec=\"size\"]');r.value='15';r.dispatchEvent(new Event('input',{bubbles:true}))}"); pg.wait_for_timeout(200)
    mem = f.evaluate(MEM)
    need(bool(mem) and round(mem.get('w', 0)) == 15, f"② 크기를 바꾸면 바뀐 값으로 기억된다 (w {mem and mem.get('w')})")
    one = f.evaluate(LOGOS)
    need(len(one) == 5 and all(v == [[SRC, round(mem['l']), round(mem['t']), 15]] for v in one.values()), f"⑨ 범위 기본 '모든 장면': 한 장면에 얹고 크기를 바꾸면 5장면 전부 같은 값 ({len(one)}장면) — 고치기 전엔 1장면")
    scope = f.evaluate("()=>[...document.querySelectorAll('[data-logo-scope]')].map(b=>[b.dataset.logoScope,b.classList.contains('active')])")
    need(scope == [['all', True], ['one', False]], f"⑨ 로고 칸에 범위 버튼 2개, 기본은 모든 장면 ({scope})")
    f.evaluate("()=>{const i=document.createElement('input');sceneStyle.show(3);sceneStyle.effect({...sceneStyle.effect(),zoom:1.4,masks:[...sceneStyle.effect().masks,{kind:'emoji',ch:'🔥',l:10,t:50,w:15,h:10,op:100}]});sceneStyle.show(0)}")
    f.evaluate("()=>{const r=document.querySelector('[data-dec=\"size\"]');r.value='16';r.dispatchEvent(new Event('input',{bubbles:true}));r.value='15';r.dispatchEvent(new Event('input',{bubbles:true}))}")
    keep = f.evaluate("()=>{const e=sceneStyle.effectAt(3);return [e.zoom,e.masks.filter(m=>m.kind==='emoji').length,e.masks.filter(m=>m.kind==='image').length]}")
    need(keep == [1.4, 1, 1], f"⑨ 전 장면에 맞출 때 다른 장면의 확대·스티커는 그대로 ({keep})")
    f.evaluate("()=>document.querySelector('[data-logo-scope=\"one\"]').click()")
    f.evaluate("()=>{sceneStyle.show(1);sceneDecorations.refresh()}"); pg.wait_for_timeout(200)
    f.evaluate("()=>{sceneStyle.effect({...sceneStyle.effect(),masks:(sceneStyle.effect().masks||[]).map(m=>m.kind==='image'?{...m,l:5}:m)})}")
    ls = sorted({v[0][1] for v in f.evaluate(LOGOS).values()}); n5 = sum(1 for v in f.evaluate(LOGOS).values() if v[0][1] == 5)
    need(ls == [5, 70] and n5 == 1, f"⑨ '이 장면만': 옮긴 장면 하나만 바뀐다 (자리 {ls}, 바뀐 장면 {n5})")
    f2 = open_job('logo-one', 4)
    need(f2.evaluate(LOGOS) == {} and f2.evaluate("()=>sceneStyle.logoScope()") == 'one', "⑨ '이 장면만'으로 쓴 뒤의 새 작업엔 자동으로 넣지 않고, 범위 선택은 기억된다")
    f2.evaluate("()=>document.querySelector('.dec-my-logo').click()"); pg.wait_for_timeout(200)
    need(list(f2.evaluate(LOGOS).keys()) == ['0'], "⑨ '이 장면만'에서 얹으면 그 장면에만")
    f2.evaluate("()=>document.querySelector('[data-logo-scope=\"all\"]').click()"); pg.wait_for_timeout(200)
    need(len(f2.evaluate(LOGOS)) == 4, "⑨ '모든 장면'을 누르면 보던 장면의 로고가 곧바로 4장면 전부에")
    f2.evaluate("()=>{const r=document.querySelector('[data-dec=\"size\"]');r.value='15';r.dispatchEvent(new Event('input',{bubbles:true}))}"); pg.wait_for_timeout(200)
    mem = f2.evaluate(MEM); f = f2
    # ⑦ 실제로 그려지나
    drawn = f.evaluate("()=>{const i=document.querySelector('.scene-decorations-top img');return i?{ok:i.complete&&i.naturalWidth>0,w:Math.round(i.getBoundingClientRect().width)}:null}")
    need(bool(drawn) and drawn['ok'] and drawn['w'] > 5, f"⑦ 로고 그림이 맨 위 층에 그려진다 ({drawn})")
    # ③ 새 작업 = 전 장면에 같은 로고
    f = open_job('logo-b', 7); got = f.evaluate(LOGOS)
    want = [SRC, round(mem['l']), round(mem['t']), 15] if mem else None
    need(len(got) == 7 and all(v == [want] for v in got.values()), f"③ 새 작업 7장면 전부에 같은 로고·자리·크기 ({len(got)}장면, 예 {next(iter(got.values()), None)}) — 고치기 전엔 0장면")
    drawn = f.evaluate("()=>{sceneStyle.show(4);sceneDecorations.refresh();const i=document.querySelector('.scene-decorations-top img');return i?{ok:i.complete&&i.naturalWidth>0}:null}")
    pg.wait_for_timeout(300); pg.screenshot(path=str(out / 'logo_memory_new_job.png'))
    need(bool(drawn), f"⑦ 새 작업 5번째 장면에도 로고가 그려진다 ({drawn})")
    snap_with = f.evaluate("()=>sceneStyle.snapshot()")
    # ⑥ 프리셋 등록에 로고가 담긴다
    f.evaluate("()=>{document.querySelector('[data-left-tab=\"mine\"]').click();document.querySelector('[data-my-save]').click()}"); pg.wait_for_timeout(400)
    preset = f.evaluate("()=>JSON.parse(localStorage.getItem('scene_style_my_presets')||'[]')[0]?.snap?.logo||null")
    need(bool(preset) and preset.get('src') == SRC and round(preset.get('w', 0)) == 15, f"⑥ 내 프리셋 등록에 로고가 담긴다 ({preset and [preset.get('src'), preset.get('w')]}) — 고치기 전엔 없다")
    # ⑤ 한 장면에서만 지우면 기억은 남는다
    f.evaluate("()=>{sceneStyle.logoScope('one');sceneStyle.show(2);sceneStyle.effect({...sceneStyle.effect(),masks:[]});sceneStyle.logoScope('all')}")
    need(f.evaluate(MEM) is not None and len(f.evaluate(LOGOS)) == 6, f"⑤ '이 장면만'으로 한 장면에서 지우면 기억은 남는다 — 다시 '모든 장면'을 눌러도 로고 없는 장면에선 아무것도 안 바뀐다(남은 {len(f.evaluate(LOGOS))}장면)")
    # ④ 저장본 있는 작업은 그대로
    bare = dict(snap_with); bare['effects'] = {}
    f = open_job('logo-c', 6, bare)
    need(f.evaluate(LOGOS) == {}, '④ 저장본이 있는 작업(로고 없이 저장)은 로고를 넣지 않는다')
    # ⑥ 그 작업에서 프리셋 적용 → 전 장면에 로고
    f.evaluate("()=>{document.querySelector('[data-left-tab=\"mine\"]').click();document.querySelector('[data-my-apply]').click()}"); pg.wait_for_timeout(700)
    got = f.evaluate(LOGOS)
    need(len(got) == 6 and all(v[0][0] == SRC and v[0][3] == 15 for v in got.values()), f"⑥ 내 프리셋 적용 → 6장면 전부에 로고 ({len(got)}장면) — 고치기 전엔 0장면")
    pg.screenshot(path=str(out / 'logo_memory_preset_apply.png'))
    # ⑤ 어느 장면에도 안 남게 지우면 잊는다
    f = open_job('logo-d', 3)
    need(len(f.evaluate(LOGOS)) == 3, '⑤ (준비) 새 작업 3장면에 로고')
    f.evaluate("()=>{sceneStyle.show(1);sceneStyle.effect({...sceneStyle.effect(),masks:[]})}")
    need(f.evaluate(LOGOS) == {} and f.evaluate(MEM) is None, "⑤ '모든 장면'에서 한 번 지우면 전 장면에서 빠지고 기억도 지워진다")
    f = open_job('logo-e', 4)
    need(f.evaluate(LOGOS) == {}, '⑤ 지운 뒤의 새 작업에는 로고가 없다')
    b.close()
srv.shutdown()

# ⑧ 결과물까지 — 편집기가 새 작업에 자동으로 넣은 그 스냅샷 그대로
from shopping_shorts import scene_style, video_assemble as va
N = 7; X0, X1, Y0, Y1 = .70, .85, .04, .125          # 로고 자리(l 70 · t 4 · w 15 · h 8.4)
def pink(png, rgba=True):
    im = Image.open(png).convert('RGBA' if rgba else 'RGB'); w, h = im.size; px = im.load(); n = 0
    for y in range(int(h * Y0), int(h * Y1), 2):
        for x in range(int(w * X0), int(w * X1), 2):
            q = px[x, y]
            if q[0] > 190 and q[1] < 90 and q[2] > 130 and (not rgba or q[3] > 120): n += 1
    return n
try:
    work = out / 'downstream'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    tts = work / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
    src = work / 'src.mp4'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', f'color=c=blue:s=1080x1920:d={N}', '-r', '30', '-pix_fmt', 'yuv420p', str(src)])
    timeline = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': f'{i}번 자막', 'caption_lines': [f'{i}번 자막'], 'tts_path': str(tts), 'target_seconds': 1,
                 'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i in range(N)]
    HEAD = {'text': '이케아도 놀랄\n한국 천재 발명품'}
    snap = scene_style.validate_snapshot(snap_with)
    kept = sum(1 for i in range(N) if any(m.get('kind') == 'image' for m in (snap['effects'].get(str(i)) or {}).get('masks') or []))
    need(kept == N, f'⑧ 서버 검증이 자동으로 들어간 로고를 {kept}/{N}장면 그대로 둔다')
    bare = scene_style.validate_snapshot({**snap_with, 'effects': {}})
    layers = scene_style.render_layers(timeline, snap, work / 'layers', HEAD, 'logoqa')
    plain = scene_style.render_layers(timeline, bare, work / 'layers0', HEAD, 'logoqa0')
    a = [pink(work / 'layers' / x['file']) for x in layers]; z = [pink(work / 'layers0' / x['file']) for x in plain]
    need(len(a) == N and min(a) > 500 and max(z) == 0, f'⑧ 렌더·캡컷 레이어 {len(a)}장 전부에 로고(자리의 분홍 점 {min(a)}~{max(a)}) / 로고 없는 스냅샷은 {max(z) if z else None}')
    one = pathlib.Path(scene_style.render_layer_one(timeline, snap, work / 'thumb', 3, HEAD, 'logoqa'))
    t = pink(one) if one.exists() else 0
    need(t > 500, f'⑧ 썸네일 한 장(4번째 장면)에 로고 (분홍 점 {t})')
    final = work / 'final.mp4'; scene_style.compose(str(src), timeline, snap, str(final), work / 'cw', HEAD)
    got = []
    for i in range(N):
        fr = work / f'f{i}.png'; va._run_ffmpeg(['ffmpeg', '-y', '-ss', str(i + 0.5), '-i', str(final), '-frames:v', '1', str(fr)]); got.append(pink(fr, rgba=False))
    need(len(got) == N and min(got) > 500, f'⑧ 완성 영상 {N}장면 전부 화면에 로고 (분홍 점 {min(got)}~{max(got)})')
finally:
    shutil.rmtree(CID_DIR, ignore_errors=True)
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
