"""자막박스 모양 [이 장면만]이 편집기 → 저장값 → 서버 검증 → 진짜 렌더러 PNG → 캡컷 초안까지 그대로 가는지 (2026-09-22 사장님 "렌더랑 캡컷까지 테스트해").
  py tools/scene_font_research/check_look_scope_render.py <출력폴더>     (8773 서버 필요, 트랙 폴더에서 띄운 것)

흐름(전부 진짜 코드): 실제 timeline(video_assemble._beat_timeline) → scene_style.context_for → 편집기(8773)에 그 컨텍스트를 넣고
  2번 장면만 [이 장면만]+검정 유리 → snapshot → scene_style.validate_snapshot → scene_style.render_layers(tools/render_scene_style.js)
  → 장면별 PNG의 자막 띠 밝기(2번=어둡다, 3번=밝다) → capcut_draft.assemble_draft_folder(scene_overlay_layers) → draft_content.json의
  scene-style-overlay 트랙 세그먼트가 장면별 PNG를 순서대로 가리키는지.
"""
import sys, json, shutil, pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
from playwright.sync_api import sync_playwright
from PIL import Image
from shopping_shorts import video_assemble as va, scene_style, capcut_draft

fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

# 재료: 1초 TTS 3개 + 3초 소스 영상(진짜 파일이어야 캡컷 조립이 복사한다)
tts = {}
for i in range(3):
    p = out / f'voice{i}.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(p)]); tts[i] = str(p)
source = out / 'source.mp4'
va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=540x960:d=3', '-r', '30', '-pix_fmt', 'yuv420p', str(source)])
caps = ['빨래 먼지까지 잡아낸', '스트레스를 요철 구조 스펀지가', '진절머리가 났던 상황을']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': tts[i], 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
timeline = va._beat_timeline(plan, tts)
headcopy = {'text': '빨래 먼지까지\n잡아낸 정체는', 'subline': '스펀지 하나로 끝'}
ctx = scene_style.context_for(timeline, headcopy, None, 'qa-look')
body_idx = [i for i, s in enumerate(ctx['scenes']) if s['kind'] == 'body']
need(len(body_idx) >= 2, f'본문 장면이 2개 이상 ({len(ctx["scenes"])}장면, 본문 {body_idx})')
A, B = body_idx[0], body_idx[1]

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?preset=t11', wait_until='networkidle')
    pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [ctx]); pg.evaluate(f'()=>window.sceneStyle.show({A})'); pg.wait_for_timeout(400)
    click = lambda sel: pg.evaluate(f"document.querySelector('{sel}').click()")
    click('[data-caption-look-scope="one"]'); click('[data-caption-look="1"]'); pg.wait_for_timeout(300)   # 검정 유리, 이 장면만
    snap = pg.evaluate('window.sceneStyle.snapshot()'); b.close()
kA, kB = f't11:story:{A}:caption', f't11:story:{B}:caption'
need((snap.get('captionLayouts') or {}).get(kA, {}).get('look') == 1 and 'look' not in (snap.get('captionLayouts') or {}).get(kB, {}), f'편집기 저장값: {A}번만 검정 유리, {B}번 기본 ({(snap.get("captionLayouts") or {}).get(kA)} / {(snap.get("captionLayouts") or {}).get(kB)})')

snap = scene_style.validate_snapshot(snap)
need((snap.get('captionLayouts') or {}).get(kA, {}).get('look') == 1, '서버 검증(validate_snapshot)을 지나도 장면별 모양이 남는다')
layers = scene_style.render_layers(timeline, snap, out / 'layers', headcopy, 'qa-look')
need(len(layers) == len(ctx['scenes']) and all(l.get('file') for l in layers), f'렌더러 PNG {len(layers)}장 = 장면 {len(ctx["scenes"])}개')

def band_brightness(png):
    """자막 띠(렌더 실측 y≈410~600/1920)의 **글자 없는 왼쪽 여백**(x 1~3%)을 평균한다 — 글자를 섞어 재면 검정 유리 108 / 흰 띠 121로 안 갈렸다."""
    im = Image.open(png).convert('RGBA'); w, h = im.size
    ys = range(int(h * .225), int(h * .305), 3); xs = range(int(w * .01), int(w * .03), 2)
    px = [im.getpixel((x, y)) for y in ys for x in xs]; px = [p for p in px if p[3] > 200]
    if not px: return None
    return sum((r + g + b) / 3 for r, g, b, a in px) / len(px)
bA = band_brightness(out / 'layers' / layers[A]['file']); bB = band_brightness(out / 'layers' / layers[B]['file'])
need(bA is not None and bB is not None and bA < 90 and bB > 200, f'렌더 PNG: {A}번 띠 어둡다(검정 유리) {bA and round(bA)} / {B}번 띠 밝다(기본 흰 띠) {bB and round(bB)}')

# 캡컷: app.py가 하는 것과 같은 모양으로 overlay 레이어를 만들어 초안을 조립한다
overlay = [{'path': str(out / 'layers' / l['file']), 'start': float(s['start']), 'end': float(s['end'])} for s, l in zip(ctx['scenes'], layers) if l.get('file')]
proj, project, files = capcut_draft.assemble_draft_folder(str(out / 'capcut'), 'C:/capcutproject/CapCut Drafts', plan=plan, timeline=timeline,
    source_video_paths={'s0': str(source)}, tts_paths=tts, project_name='look-scope-qa', scene_overlay_layers=overlay)
draft = json.loads((pathlib.Path(proj) / 'draft_content.json').read_text(encoding='utf-8'))
track = next((t for t in draft.get('tracks', []) if t.get('name') == 'scene-style-overlay'), None)
need(track is not None and len(track['segments']) == len(overlay), f'캡컷 초안에 scene-style-overlay 트랙 세그먼트 {track and len(track["segments"])}개 = 레이어 {len(overlay)}개')
mats = {m['id']: m for m in draft.get('materials', {}).get('videos', [])}
seg_paths = [mats.get(sg['material_id'], {}).get('path', '') for sg in (track or {}).get('segments', [])]
# 캡컷 조립은 PNG를 scene-style-000N.png로 이름을 바꿔 복사한다 — 순서(N=장면 순)와 구간(start/end)으로 대조
segs = (track or {}).get('segments', [])
starts = [round(sg['target_timerange']['start'] / 1e6, 3) for sg in segs]
need(len(set(seg_paths)) == len(seg_paths) and starts == [round(o['start'], 3) for o in overlay], f'세그먼트가 장면 순서대로 서로 다른 PNG·구간을 가리킨다 ({[p.rsplit("/",1)[-1] for p in seg_paths]}, 시작 {starts})')
copied = [f for f in files if str(f).endswith('.png')]
need(all((pathlib.Path(proj) / pathlib.Path(p).name).exists() for p in seg_paths), f'초안 폴더에 PNG가 실제로 복사됐다 ({len(copied)}개)')
# 복사된 PNG도 원본과 같은 밝기(엉뚱한 파일이 아닌지)
cA = band_brightness(pathlib.Path(proj) / pathlib.Path(seg_paths[A]).name); cB = band_brightness(pathlib.Path(proj) / pathlib.Path(seg_paths[B]).name)
need(cA is not None and cB is not None and cA < 90 and cB > 200, f'캡컷 폴더 PNG 띠 밝기: {A}번 {cA and round(cA)} / {B}번 {cB and round(cB)}')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
