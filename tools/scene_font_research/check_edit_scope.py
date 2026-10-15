# -*- coding: utf-8 -*-
"""[적용 범위: 모든 장면 | 이 장면만] 스위치 하나가 자막·제목·채널명의 글자크기·↑↓를 정하고, 그 결과가
편집기 → 저장값 → 서버 검증 → 진짜 렌더러 PNG → 캡컷 초안까지 그대로 가는지 (2026-09-28 사장님
"자막 제목 채널명 등등 이 장면만 등록이나 전체 등록이나 해야 한다 / 렌더랑 캡컷까지 라이브하고 검증까지").

  py tools/scene_font_research/check_edit_scope.py <출력폴더>     (8773 서버 = 트랙 폴더에서 py -m http.server 8773 --bind 127.0.0.1)

고치기 전 코드에서는: 스위치가 없어 ①부터 실패하고, 제목·채널명은 장면별 키가 없어 ③④⑤가 실패한다.
흐름: 실제 timeline(video_assemble._beat_timeline) → scene_style.context_for → 편집기(8773)에서 버튼을 누른다 →
  snapshot → scene_style.validate_snapshot → scene_style.render_layers(tools/render_scene_style.js) → 장면별 PNG의
  제목·채널명 영역 픽셀 대조(B만 다르고 A=C) → capcut_draft.assemble_draft_folder(scene_overlay_layers) → 세그먼트·복사본 대조.
"""
import sys, json, hashlib, pathlib, shutil
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8773
# 라이브 편집기로 돌리려면: SCENE_QA_URL=https://shoppingshorts.duckdns.org/api/produce/scene-style/assets/out/scene-style-ui-showcase.html
import os
BASE = os.environ.get('SCENE_QA_URL') or f'http://127.0.0.1:{PORT}/out/scene-style-ui-showcase.html'
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
from shopping_shorts import video_assemble as va, scene_style, capcut_draft

fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

# 재료: 1초 TTS 4개 + 4초 소스 영상(훅 1 + 본문 3)
tts = {}
for i in range(4):
    p = out / f'voice{i}.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(p)]); tts[i] = str(p)
source = out / 'source.mp4'
va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=540x960:d=4', '-r', '30', '-pix_fmt', 'yuv420p', str(source)])
caps = ['빨래 먼지까지 잡아낸', '스트레스를 요철 구조 스펀지가', '진절머리가 났던 상황을', '이제는 한 번에 끝난다']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': tts[i], 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
timeline = va._beat_timeline(plan, tts)
headcopy = {'text': '빨래 먼지까지\n잡아낸 정체는', 'subline': '스펀지 하나로 끝'}
ctx = scene_style.context_for(timeline, headcopy, None, 'qa-scope')
body_idx = [i for i, s in enumerate(ctx['scenes']) if s['kind'] == 'body']
need(len(body_idx) >= 3, f'본문 장면이 3개 이상 ({len(ctx["scenes"])}장면, 본문 {body_idx})')
A, B, C = body_idx[0], body_idx[1], body_idx[2]

rects = {}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(BASE + '?preset=t11', wait_until='networkidle')
    pg.evaluate('([c])=>window.sceneStyle.load(c,null)', [ctx]); pg.wait_for_timeout(400)
    show = lambda i: (pg.evaluate(f'window.sceneStyle.show({i})'), pg.wait_for_timeout(250))
    click = lambda sel: pg.evaluate(f"(()=>{{const e=document.querySelector('{sel}');if(!e)return false;e.click();return true}})()")
    scope = lambda v: click(f'[data-edit-scope="{v}"]')
    step = lambda field, kind, val: click(f'[data-field-key="{field}"] [data-{kind}="{val}"]')
    snap = lambda: pg.evaluate('window.sceneStyle.snapshot()')
    output = lambda field: pg.evaluate(f"document.querySelector('[data-field-key=\"{field}\"] .font-stepper output')?.textContent")
    def measure(bind):
        return pg.evaluate(f"""(()=>{{const pv=document.querySelector('#a-live-preview')||document.querySelector('.precision-edit-layer').parentElement;
          const e=pv.querySelector('.precision-text[data-edit-bind="{bind}"]');if(!e)return null;const r=e.getBoundingClientRect(),q=pv.getBoundingClientRect();
          return {{fs:parseFloat(getComputedStyle(e).fontSize),x:(r.left-q.left)/q.width,y:(r.top-q.top)/q.height,w:r.width/q.width,h:r.height/q.height}}}})()""")

    # ① 스위치가 있고, '모든 장면'에서 자막 글자를 키우면 본문 전 장면의 자막 키에 같은 값이 들어간다
    show(A); has = scope('all')
    need(has, '문구/텍스트 패널에 [적용 범위] 스위치([data-edit-scope])가 있다')
    step('caption', 'font-step', '0.1'); step('caption', 'font-step', '0.1'); pg.wait_for_timeout(200)
    fs = snap().get('fontScales') or {}
    vals = [fs.get(f't11:body:caption:{i}') for i in body_idx]
    need(all(v is not None and abs(v - 1.5) < .01 for v in vals), f'모든 장면: 본문 자막 크기 키가 전 장면에 1.5 ({vals})')

    # ② '이 장면만'으로 C의 제목을 키운 뒤(110%) '모든 장면'으로 다시 키우면 — 보이는 값+10%=120%가 공통 키가 되고 C의 장면별 키는 지워진다(전체가 이긴다)
    show(C); scope('one'); step('bodyTitle', 'font-step', '0.1'); pg.wait_for_timeout(150)
    fs = snap().get('fontScales') or {}
    need(abs((fs.get(f't11:body:bodyTitle:{C}') or 0) - 1.1) < .01 and 't11:body:bodyTitle' not in fs, f'이 장면만: 제목 크기가 C의 장면별 키에만 ({ {k: v for k, v in fs.items() if "bodyTitle" in k} })')
    scope('all'); step('bodyTitle', 'font-step', '0.1'); pg.wait_for_timeout(150)
    fs = snap().get('fontScales') or {}
    need(abs((fs.get('t11:body:bodyTitle') or 0) - 1.2) < .01 and f't11:body:bodyTitle:{C}' not in fs, f'모든 장면: 제목 크기가 공통 키 1.2(보이던 1.1+0.1), C의 장면별 키는 지워짐 ({ {k: v for k, v in fs.items() if "bodyTitle" in k} })')

    # ③ '이 장면만'으로 B의 제목을 3번 키우고 채널명을 2번 내린다 → B의 장면별 키만 생기고 공통 키는 그대로
    show(B); scope('one')
    for _ in range(3): step('bodyTitle', 'font-step', '0.1')
    for _ in range(2): step('channel', 'position-step', '1')
    pg.wait_for_timeout(200)
    s = snap(); fs = s.get('fontScales') or {}; to = s.get('textOffsets') or {}
    need(abs((fs.get(f't11:body:bodyTitle:{B}') or 0) - 1.5) < .01 and abs((fs.get('t11:body:bodyTitle') or 0) - 1.2) < .01, f'이 장면만: B 제목 1.5(장면별) / 공통 1.2 유지 ({ {k: v for k, v in fs.items() if "bodyTitle" in k} })')
    need(abs((to.get(f't11:body:channel:{B}') or 0) - 1.0) < .01 and 't11:body:channel' not in to, f'이 장면만: B 채널명 ↓ 1.0(장면별), 공통 키 없음 ({ {k: v for k, v in to.items() if "channel" in k} })')
    need(output('bodyTitle') == '150%', f'B의 제목 스텝퍼 표시 150% ({output("bodyTitle")})')
    mB = measure('bodyTitle'); cB = measure('channel')
    show(A); mA = measure('bodyTitle'); cA = measure('channel')
    need(output('bodyTitle') == '120%', f'A의 제목 스텝퍼 표시 120% ({output("bodyTitle")})')
    need(mA and mB and mB['fs'] > mA['fs'] * 1.2, f'편집기 화면: B 제목 글자 {mB and round(mB["fs"], 1)}px > A {mA and round(mA["fs"], 1)}px')
    need(cA and cB and cB['y'] > cA['y'] + 0.005, f'편집기 화면: B 채널명이 A보다 아래 (y {cB and round(cB["y"], 3)} > {cA and round(cA["y"], 3)})')
    rects = {'title': mB, 'titleA': mA, 'channel': cB, 'channelA': cA}
    final = snap(); b.close()
    # 서버에서 진짜 렌더러로 다시 돌릴 수 있게 남긴다(check_edit_scope_render.py <출력폴더> 가 읽는다)
    (out / 'snapshot.json').write_text(json.dumps(final, ensure_ascii=False), encoding='utf-8')
    (out / 'rects.json').write_text(json.dumps({'rects': rects, 'A': A, 'B': B, 'C': C}, ensure_ascii=False), encoding='utf-8')
    need(not errs, f'페이지 오류 없음 ({errs[:2]})')

# ④ 서버 검증 → 진짜 렌더러 PNG: 제목·채널명 영역이 B만 다르고 A=C
snap = scene_style.validate_snapshot(final)
need(abs((snap.get('fontScales') or {}).get(f't11:body:bodyTitle:{B}', 0) - 1.5) < .01, '서버 검증(validate_snapshot)을 지나도 장면별 키가 남는다')
layers = scene_style.render_layers(timeline, snap, out / 'layers', headcopy, 'qa-scope')
need(len(layers) == len(ctx['scenes']) and all(l.get('file') for l in layers), f'렌더러 PNG {len(layers)}장 = 장면 {len(ctx["scenes"])}개')

def region_diff(pa, pb, r, ra):
    """두 PNG에서 요소 영역(둘 중 큰 쪽으로 합침, 위아래 20% 여유)의 평균 픽셀 차."""
    ia = Image.open(pa).convert('RGB'); ib = Image.open(pb).convert('RGB'); w, h = ia.size
    x0 = min(r['x'], ra['x']); y0 = min(r['y'], ra['y']); x1 = max(r['x'] + r['w'], ra['x'] + ra['w']); y1 = max(r['y'] + r['h'], ra['y'] + ra['h'])
    pad = (y1 - y0) * .2; box = (int(x0 * w), max(0, int((y0 - pad) * h)), int(x1 * w), min(h, int((y1 + pad) * h)))
    d = ImageChops.difference(ia.crop(box), ib.crop(box)).convert('L')
    px = list(d.getdata()); return sum(px) / len(px)
pngs = {i: out / 'layers' / layers[i]['file'] for i in (A, B, C)}
tAB = region_diff(pngs[A], pngs[B], rects['title'], rects['titleA']); tAC = region_diff(pngs[A], pngs[C], rects['title'], rects['titleA'])
cAB = region_diff(pngs[A], pngs[B], rects['channel'], rects['channelA']); cAC = region_diff(pngs[A], pngs[C], rects['channel'], rects['channelA'])
need(tAC < 1.0 and tAB > max(4.0, tAC * 4), f'렌더 PNG 제목 영역: A↔C 같다 {tAC:.2f} / A↔B 다르다 {tAB:.2f}')
need(cAC < 1.0 and cAB > max(4.0, cAC * 4), f'렌더 PNG 채널명 영역: A↔C 같다 {cAC:.2f} / A↔B 다르다 {cAB:.2f}')

# ⑤ 캡컷: app.py가 하는 것과 같은 모양으로 overlay 레이어를 만들어 초안을 조립한다
overlay = [{'path': str(out / 'layers' / l['file']), 'start': float(s['start']), 'end': float(s['end'])} for s, l in zip(ctx['scenes'], layers) if l.get('file')]
proj, project, files = capcut_draft.assemble_draft_folder(str(out / 'capcut'), 'C:/capcutproject/CapCut Drafts', plan=plan, timeline=timeline,
    source_video_paths={'s0': str(source)}, tts_paths=tts, project_name='edit-scope-qa', scene_overlay_layers=overlay)
draft = json.loads((pathlib.Path(proj) / 'draft_content.json').read_text(encoding='utf-8'))
track = next((t for t in draft.get('tracks', []) if t.get('name') == 'scene-style-overlay'), None)
need(track is not None and len(track['segments']) == len(overlay), f'캡컷 초안에 scene-style-overlay 트랙 세그먼트 {track and len(track["segments"])}개 = 레이어 {len(overlay)}개')
mats = {m['id']: m for m in draft.get('materials', {}).get('videos', [])}
seg_paths = [mats.get(sg['material_id'], {}).get('path', '') for sg in (track or {}).get('segments', [])]
starts = [round(sg['target_timerange']['start'] / 1e6, 3) for sg in (track or {}).get('segments', [])]
need(len(set(seg_paths)) == len(seg_paths) and starts == [round(o['start'], 3) for o in overlay], f'세그먼트가 장면 순서대로 서로 다른 PNG·구간을 가리킨다 (시작 {starts})')
md5 = lambda p: hashlib.md5(pathlib.Path(p).read_bytes()).hexdigest()
copiedB = pathlib.Path(proj) / pathlib.Path(seg_paths[B]).name if seg_paths else None
need(copiedB and copiedB.exists() and md5(copiedB) == md5(pngs[B]), f'캡컷 폴더의 B 장면 PNG가 렌더 PNG와 같은 파일(md5 일치)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
