# -*- coding: utf-8 -*-
"""원본에서 제목이 빈칸으로 저장된 작업을 템플릿(썰쇼핑)으로 바꾸면 자동 제목이 돌아오나 (2026-09-25 사장님 "썰쇼핑 돌려놓고").
  py tools/scene_font_research/check_empty_titles.py <출력폴더>      (8773 서버 필요)
 실측 사례 job cafa17d6856b: presetId plain, hook1·hook2·bodyTitle 모두 "" → 이븐쇼핑으로 바꾸면 빈 제목 띠.
 ① 원본 그대로면 제목 없음(인스타식 — 그대로) ② 이븐쇼핑을 누르면 자동 제목 ③ 렌더 레이어에도 제목 ④ 일부만 비운 제목은 존중
"""
import sys, json, pathlib, shutil
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble as va
from PIL import Image
out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
tl = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': n, 'caption_lines': [n], 'tts_path': str(tts), 'target_seconds': 1, 'role': r}
      for i, (n, r) in enumerate([('프로게이머도 예상 못한 미친 활용법', 'hook'), ('과자 한번 집어 먹을 때마다', 'body'), ('손가락이 끈적해지죠', 'body')])]
EMPTY = {'channel': '숏템메이커', 'hook1': '', 'hook2': '', 'bodyTitle': '', 'caption': ''}
saved = {'version': 1, 'plainCaption': 2, 'mode': 'story', 'presetId': 'plain', 'sceneIndex': 0, 'frameKind': 'hook', 'text': EMPTY}
ctx = scene_style.context_for(tl, {'text': ''}, scene_style.validate_snapshot(dict(saved)))
T = "()=>{const t=window.sceneStyle.snapshot()?.text||{};return [t.hook1,t.hook2,t.bodyTitle]}"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 1600}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)', [ctx, saved]); pg.wait_for_timeout(800)
    t0 = pg.evaluate(T); need(t0 == ['', '', ''], f'① 원본(인스타식)은 빈 제목 그대로 {t0}')
    pg.click('[data-p20]'); pg.wait_for_timeout(800)   # 첫 템플릿 카드(이븐쇼핑)
    t1 = pg.evaluate(T); pid = pg.evaluate('window.sceneStyle.snapshot().presetId')
    need(pid != 'plain' and t1[0] and '프로게이머' in (t1[0] + t1[1]), f'② 템플릿({pid})을 누르면 자동 제목 {t1}')
    pg.locator('#a-live-preview').screenshot(path=str(out / 'template_hook.png'))
    snap = scene_style.validate_snapshot(json.loads(json.dumps(pg.evaluate('window.sceneStyle.snapshot()'))))
    need(not errs, f'페이지 오류 {errs[:3]}'); b.close()
# ③ 렌더: 편집기가 저장한 값으로 훅 레이어 위쪽에 제목 글자
lay = scene_style.render_layers(tl, snap, out / 'layers', {'text': ''}, 'etqa')
im = Image.open(out / 'layers' / lay[0]['file']).convert('RGBA'); W, H = im.size
ink = sum(1 for y in range(int(H * .08), int(H * .30), 3) for x in range(int(W * .1), int(W * .9), 6) if (lambda c: c[3] > 200 and c[0] > 200 and c[1] > 200)(im.getpixel((x, y))))
need(ink > 150, f'③ 렌더 훅 레이어에 제목 글자가 찍힌다 (밝은 점 {ink})')
# ④ 서버: 템플릿인데 저장본 제목이 전부 빈칸이면(렌더가 직접 저장본을 읽는 경우) 자동 제목
t4 = scene_style.context_for(tl, {'text': ''}, dict(saved, presetId='t11'))['text']
need(t4['hook1'] and '프로게이머' in t4['hook1'] + t4['hook2'], f'④ 서버: 템플릿 저장본의 빈 제목은 자동 제목으로 {t4["hook1"]}/{t4["hook2"]}')
t5 = scene_style.context_for(tl, {'text': ''}, dict(saved, presetId='t11', text=dict(EMPTY, hook1='내 제목')))['text']
need(t5['hook1'] == '내 제목' and t5['hook2'] == '', f'④ 일부만 비운 제목은 존중 {t5["hook1"]}/{t5["hook2"]}')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건'); sys.exit(1 if fails else 0)
