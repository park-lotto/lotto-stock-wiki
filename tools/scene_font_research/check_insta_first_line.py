# -*- coding: utf-8 -*-
"""인스타 대본 = 첫 장면부터 자막이 **렌더·썸네일·최종 mp4까지** 나오는가 (2026-09-25 사장님, 0순위-A1a).
  py tools/scene_font_research/check_insta_first_line.py <출력폴더>
같은 타임라인을 썰(표식 없음)/인스타(title_line=False)로 두 번 렌더해 첫 장면을 비교한다.
  썰: 첫 장면 = 훅 레이어(자막 없음) / 인스타: 첫 장면 = 본문 레이어(자막 글자 있음)
"""
import sys, pathlib, shutil, json
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble as va
from PIL import Image
out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
src = out / 'src.mp4'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1080x1920:d=2', '-r', '30', '-pix_fmt', 'yuv420p', str(src)])
CAPS = ['아니 요즘 거실 싸움이 멈추질 않아요', '이거 하나로 싹 끝났어요']
def timeline(insta):
    tl = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
           'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(CAPS)]
    if insta: tl[0]['title_line'] = False
    return tl
TEXT = {'channel': '숏템메이커', 'hook1': '거실 싸움 끝낸', 'hook2': '천재 아이디어', 'bodyTitle': '거실 싸움 끝낸 천재 아이디어'}
snap = scene_style.validate_snapshot({'version': 1, 'mode': 'story', 'presetId': 't11', 'sceneIndex': 0, 'frameKind': 'hook', 'text': TEXT})
HEAD = {'text': '거실 싸움 끝낸\n천재 아이디어'}
R = {}
for name, insta in (('sul', False), ('insta', True)):
    d = out / name; tl = timeline(insta)
    kinds = [s['kind'] for s in scene_style.context_for(tl, HEAD, snap)['scenes']]
    lay = scene_style.render_layers(tl, snap, d / 'layers', HEAD, 'ifqa')
    pngs = [d / 'layers' / l['file'] for l in lay if l.get('file')]
    one = pathlib.Path(scene_style.render_layer_one(tl, snap, d / 'thumb', 0, HEAD, 'ifqa'))
    final = d / 'final.mp4'; scene_style.compose(str(src), tl, snap, str(final), d / 'cw', HEAD)
    fr = d / 'f0.png'; va._run_ffmpeg(['ffmpeg', '-y', '-ss', '0.5', '-i', str(final), '-frames:v', '1', str(fr)])
    R[name] = {'kinds': kinds, 'layer0': pngs[0], 'layer1': pngs[1] if len(pngs) > 1 else None, 'thumb0': one, 'frame0': fr}
    print(f'  {name}: 장면 종류 {kinds}')
def same(a, b):   # 두 PNG가 같은 그림인가(알파 포함 차이 픽셀 비율)
    A = Image.open(a).convert('RGBA').resize((270, 480)); B = Image.open(b).convert('RGBA').resize((270, 480))
    diff = sum(1 for p, q in zip(A.getdata(), B.getdata()) if sum(abs(x - y) for x, y in zip(p, q)) > 60)
    return diff / (270 * 480)
s, i = R['sul'], R['insta']
need(s['kinds'][0] == 'hook' and all(k == 'body' for k in i['kinds']), f'① 장면 종류: 썰 첫 장면=hook / 인스타 전부 body')
d_sul = same(s['layer0'], s['layer1']); d_ins = same(i['layer0'], s['layer1'])
print(f'    첫 레이어 vs 썰 본문 레이어 차이: 썰 {d_sul:.3f} / 인스타 {d_ins:.3f}')
need(d_sul > 0.05 and d_ins < d_sul / 3, '② 렌더 레이어: 인스타 첫 장면은 본문 모양(썰 첫 장면은 훅 모양)')
t_ins = same(i['thumb0'], i['layer0'])
need(t_ins < 0.01, f'③ 썸네일 한 장도 렌더 레이어와 같다 (차이 {t_ins:.3f})')
f_diff = same(s['frame0'], i['frame0'])
need(f_diff > 0.03, f'④ 최종 mp4 첫 장면이 썰과 다르게 나온다 (차이 {f_diff:.3f})')
for n in ('sul', 'insta'): shutil.copy(R[n]['frame0'], out / f'frame0_{n}.png')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건'); sys.exit(1 if fails else 0)
