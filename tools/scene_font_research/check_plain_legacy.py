# -*- coding: utf-8 -*-
"""이미 저장된 원본(plain) 작업은 예전 그대로, 새 원본은 새 방식(2026-09-25 사장님 B안).
  py tools/scene_font_research/check_plain_legacy.py <출력폴더>      (8773 서버 필요)
 새 방식 = 자막 제목 바로 아래(22%)·박스 없음, 스냅샷에 plainCaption:2.  표시 없는 옛 스냅샷 = 아래(81%)·예전 검정 박스.
 편집기와 렌더러(render_layers)가 같은 load를 쓰므로 둘 다 잰다.
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
TEXT = {'channel': '숏템메이커', 'hook1': '제목 첫줄', 'hook2': '제목 둘째', 'bodyTitle': '본문 제목'}
base = {'version': 1, 'mode': 'story', 'presetId': 'plain', 'sceneIndex': 0, 'frameKind': 'hook', 'text': TEXT}
legacy = dict(base); new = dict(base, plainCaption=2)
legacy_drag = dict(base, captionDrags={'plain:story:2:caption': {'x': 0, 'y': -13.5}})
CAP = "#a-live-preview .precision-text[data-edit-bind=caption]"
PATCH = "#a-live-preview .precision-patch[data-edit-bind=caption]"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 1600}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    def load(snap): pg.evaluate('s=>window.sceneStyle.load(window.sceneStyle.context(),s)', snap); pg.evaluate('window.sceneStyle.show(2)'); pg.wait_for_timeout(400)
    top = lambda: pg.evaluate(f"(()=>{{const e=document.querySelector('{CAP}');const r=document.querySelector('#a-live-preview').getBoundingClientRect();return Math.round((e.getBoundingClientRect().top-r.top)/r.height*1000)/10}})()")
    bg = lambda: pg.evaluate(f"getComputedStyle(document.querySelector('{PATCH}')).backgroundColor")
    load(legacy); t, c = top(), bg(); s = pg.evaluate('window.sceneStyle.snapshot()')
    need(t > 75 and c == 'rgb(0, 0, 0)' and 'plainCaption' not in s, f'① 옛 원본 = 예전 그대로: 자막 {t}%, 박스 {c}, 표시 없음 유지')
    load(legacy_drag); t = top()
    need(abs(t - (81.25 - 13.5)) < 2.5, f'② 옛 원본에서 끌어 옮긴 자리 그대로 {t}% (예전 계산 {81.25 - 13.5})')
    load(new); t, c = top(), bg()
    need(18 <= t <= 26 and c == 'rgba(0, 0, 0, 0)', f'③ 새 원본 = 제목 아래 {t}%, 박스 없음 {c}')
    load(legacy); pg.click('[data-none]'); pg.wait_for_timeout(600); pg.evaluate('window.sceneStyle.show(2)'); pg.wait_for_timeout(300)
    t, s = top(), pg.evaluate('window.sceneStyle.snapshot()')
    need(18 <= t <= 26 and s.get('plainCaption') == 2, f'④ 옛 작업에서 원본 카드를 다시 누르면 새 방식 {t}%, 표시 {s.get("plainCaption")}')
    need(not errs, f'페이지 오류 {errs[:3]}'); b.close()
# ⑤ 서버 검증
ok2 = scene_style.validate_snapshot(dict(new)).get('plainCaption') == 2
try: scene_style.validate_snapshot(dict(base, plainCaption=3)); bad = False
except ValueError: bad = True
need(ok2 and bad, f'⑤ 서버: plainCaption 2는 보존, 다른 값은 거절 ({ok2}, {bad})')
# ⑥ 렌더러
tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
tl = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': f'자막 {i}번 문장', 'caption_lines': [f'자막 {i}번 문장'], 'tts_path': str(tts), 'target_seconds': 1, 'role': 'hook' if i == 0 else 'body'} for i in range(3)]
def cap_rows(snap, tag):
    lay = scene_style.render_layers(tl, scene_style.validate_snapshot(dict(snap)), out / tag, {'text': '제목 첫줄'}, 'lgqa')
    im = Image.open(out / tag / lay[2]['file']).convert('RGBA'); W, H = im.size
    rows = [y * 100 / H for y in range(0, H, 4) if sum(1 for x in range(int(W * .1), int(W * .9), 8) if im.getpixel((x, y))[3] > 40) > 5]
    edge = sum(1 for y in range(0, H, 4) for x in (int(W * .02),) if im.getpixel((x, y))[3] > 200 and y / H > .15)
    return [r for r in rows if r > 15], edge
rl, el = cap_rows(legacy, 'legacy'); rn, en = cap_rows(new, 'new')
need(rl and min(rl) > 75 and el > 10, f'⑥ 렌더 — 옛 원본: 자막 {round(min(rl),1) if rl else None}% 부근 · 가장자리까지 박스 {el}점')
need(rn and 18 <= min(rn) <= 30 and en == 0, f'⑥ 렌더 — 새 원본: 자막 {round(min(rn),1) if rn else None}% 부근 · 박스 없음 {en}점')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건'); sys.exit(1 if fails else 0)
