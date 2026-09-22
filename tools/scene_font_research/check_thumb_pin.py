# -*- coding: utf-8 -*-
"""새 편집기의 [🖼 이 장면을 썸네일 후보로] — 진짜 앱(격리 DB)으로 끝까지 확인한다. 가짜 응답 없음.
  ../../.venv/Scripts/python.exe tools/scene_font_research/check_thumb_pin.py <출력폴더>
하는 일: 격리 DB·작업폴더에 3장면짜리 job을 만들고(qa_scene_style_render.py와 같은 방식) 앱을 127.0.0.1:8774에 띄운다 →
  ① 편집기 단독: 서버의 실제 context로 열어 3번째 장면에서 버튼 클릭 → DB thumbnail.pins·pin_*.jpg 파일·이미지 응답 확인
  ② 제작소(produce.html) 안에서: 회색 버튼으로 편집기를 열고 → 핀 → [썸네일 단계로 이동] → 팝업이 닫히고 7단계로 가는지
라이브 DB·외부 API는 쓰지 않는다.
"""
import sys, json, time, shutil, threading, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn
from PIL import Image
from playwright.sync_api import sync_playwright

JOB, PORT = 'scene-font-qa', 8774
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

# 장면마다 색이 다른 3초 영상 — 어느 장면이 핀으로 갔는지 색으로 가린다(빨강/초록/파랑)
source = work / 'source.mp4'
va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=540x960:d=1', '-f', 'lavfi', '-i', 'color=c=green:s=540x960:d=1', '-f', 'lavfi', '-i', 'color=c=blue:s=540x960:d=1',
                '-filter_complex', '[0][1][2]concat=n=3:v=1:a=0', '-r', '30', '-pix_fmt', 'yuv420p', str(source)])
tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
caps = ['첫 번째 실제 자막', '두 번째 실제 자막', '마지막 실제 자막']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work
module._THUMB_DIR = work / '_thumbs'   # ★안 돌리면 핀 파일이 진짜 shopping_shorts/data/thumbs 에 생긴다(1차 실행에서 그랬다)
(work / JOB / 's0').mkdir(parents=True); shutil.copyfile(source, work / JOB / 's0' / 'source.mp4')
store = Store(module.DB_PATH); store.create_mix_job(JOB, [], 3, 'free'); store.update_mix_job(JOB, edit_plan=plan)

server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(100):
    if server.started: break
    time.sleep(.2)
BASE = f'http://127.0.0.1:{PORT}'
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 1200}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        # ── ① 편집기 단독(서버가 주는 진짜 자산·진짜 context)
        pg.goto(f'{BASE}/api/produce/scene-style/assets/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
        need(pg.locator('[data-thumb-pin]').is_visible(), '① 미리보기 아래에 [이 장면을 썸네일 후보로] 버튼이 보인다')
        pg.click('[data-thumb-pin]'); pg.wait_for_timeout(300)
        need('샘플' in pg.inner_text('[data-thumb-msg]') and not (Store(module.DB_PATH).get_mix_job(JOB).get('thumbnail') or {}).get('pins'), '① 실제 영상 없이 누르면 안내만 하고 서버에 아무것도 안 보낸다')
        ctx = pg.evaluate(f"fetch('/api/produce/scene-style/context/{JOB}').then(r=>r.json())"); scenes = ctx['context']['scenes']
        print('  서버 context 장면:', [(s['beat_idx'], s['kind']) for s in scenes])
        pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)', [ctx['context'], ctx.get('snapshot')]); pg.wait_for_timeout(500)
        target = next(i for i, s in enumerate(scenes) if s['beat_idx'] == 2)
        pg.evaluate(f'window.sceneStyle.show({target})'); pg.wait_for_timeout(300); pg.click('[data-thumb-pin]')
        pg.wait_for_function("document.querySelector('[data-thumb-msg]').textContent.startsWith('✓')||document.querySelector('[data-thumb-msg]').textContent.startsWith('✕')", timeout=60000)
        print('  화면 안내:', pg.inner_text('[data-thumb-msg]'))
        pins = (Store(module.DB_PATH).get_mix_job(JOB).get('thumbnail') or {}).get('pins') or []
        need(len(pins) == 1 and pins[0]['beat_idx'] == 2, f'① DB thumbnail.pins에 3번째 장면(beat_idx 2)이 들어갔다 {pins}')
        f = (module._THUMB_DIR / JOB / pins[0]['name']) if pins else None; f = f if f and f.exists() else None
        need(bool(f) and f.stat().st_size > 1000, f'① 핀 파일이 실제로 생겼다 {f.name if f else None}')
        if f:
            r, g, bl = Image.open(f).convert('RGB').resize((1, 1)).getpixel((0, 0)); need(bl > 150 and r < 90 and g < 90, f'① 그 파일은 3번째 장면 화면이다(파랑) rgb=({r},{g},{bl})')
            need(pg.evaluate(f"fetch('/api/produce/thumb/file/{JOB}/{pins[0]['name']}').then(r=>r.status)") == 200, '① 썸네일 후보 이미지 주소가 200으로 열린다')
        need(pg.locator('[data-thumb-go]').is_visible(), '① 보낸 뒤 [썸네일 단계로 이동] 버튼이 나타난다')
        pg.evaluate(f'window.sceneStyle.show({target})'); pg.click('[data-thumb-pin]'); pg.wait_for_timeout(1500)
        need(len((Store(module.DB_PATH).get_mix_job(JOB).get('thumbnail') or {}).get('pins') or []) == 1, '① 같은 장면을 두 번 보내도 후보가 중복으로 쌓이지 않는다')
        pg.locator('.scene-thumb-pin').screenshot(path=str(out / 'thumb_pin_bar.png'))
        # ── ② 제작소 안에서(부모 연결)
        pg2 = b.new_page(viewport={'width': 1600, 'height': 1200}); pg2.on('pageerror', lambda e: errs.append('제작소:' + str(e)))
        pg2.goto(f'{BASE}/produce.html', wait_until='domcontentloaded'); pg2.wait_for_timeout(2500)
        ready = pg2.evaluate("typeof openSceneStyleEditor==='function'&&typeof stepGo==='function'")
        need(ready, '② 제작소에 openSceneStyleEditor·stepGo가 있다')
        if ready:
            # 6단계까지 온 고객은 이미 미리보기를 확인한 상태다(그래야 6단계 자체가 열린다 — produce.html stepLocked/canGoNext).
            #   시험 job은 그 과정을 안 밟았으므로 같은 상태(PREVIEW_STATUS='ready')를 만들어 준다. 잠금 규칙 자체는 건드리지 않는다.
            pg2.evaluate(f"MIX_JOB='{JOB}';PREVIEW_STATUS='ready'"); pg2.evaluate('openSceneStyleEditor()'); pg2.wait_for_timeout(4000)
            fr = next((x for x in pg2.frames if 'scene-style-ui-showcase' in x.url), None); need(fr is not None, '② 회색 버튼 경로로 편집기 팝업이 열린다')
            if fr:
                fr.wait_for_function('window.sceneStyle&&window.sceneStyle.context()&&window.sceneStyle.context().jobId', timeout=30000)
                fr.evaluate('window.sceneStyle.show(1)'); fr.click('[data-thumb-pin]'); fr.wait_for_function("document.querySelector('[data-thumb-msg]').textContent.startsWith('✓')", timeout=60000)
                need(len((Store(module.DB_PATH).get_mix_job(JOB).get('thumbnail') or {}).get('pins') or []) == 2, '② 제작소 안에서 보낸 핀도 DB에 들어갔다(합계 2)')
                before = pg2.evaluate("document.querySelector('dialog[open]')!==null"); fr.click('[data-thumb-go]'); pg2.wait_for_timeout(2500)
                after = pg2.evaluate("document.querySelector('dialog[open]')!==null"); need(before and not after, f'② [썸네일 단계로 이동] → 편집기 팝업이 닫힌다 (열림 {before}→{after})')
                st = pg2.evaluate("({cur:cur,thumbPanel:PANEL_BY_KEY.thumb,locked:stepLocked(PANEL_BY_KEY.thumb),lockMsg:stepLocked(PANEL_BY_KEY.thumb)?stepLockMsg():''})"); print('  이동 뒤 제작소 상태:', st)
                # 제작소 규칙: 잠긴 단계(앞 단계 미완)로는 jump가 안 간다. 시험 job은 앞 단계를 안 밟았으므로 잠겨 있을 수 있다 → 그때는 '잠금 안내가 떴는가'를 본다.
                if st['locked']: need(bool(st['lockMsg']), f"② 7단계가 잠긴 job — 제작소 잠금 규칙대로 이동을 막고 안내한다: {st['lockMsg']}")
                else: need(st['cur'] == st['thumbPanel'], f"② 제작소가 7단계(썸네일) 패널로 이동했다 cur={st['cur']}")
                pg2.screenshot(path=str(out / 'after_goto_thumb.png'))
        need(not errs, f'페이지 오류 {errs[:4]}'); b.close()
finally:
    server.should_exit = True; time.sleep(1)
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
