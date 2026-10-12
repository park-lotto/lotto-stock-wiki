# -*- coding: utf-8 -*-
"""자막박스 색·투명도가 **렌더·썸네일·최종합성**까지 따라가나 (2026-09-24 고객 데이워커님, 0순위-A1a).
  py tools/scene_font_research/check_caption_box_downstream.py <출력폴더>
박스색 #ff2266을 투명도 0% / 60%로 두 번 렌더해 같은 자리의 픽셀을 비교한다.
  ② render_layers(렌더·캡컷)   : 박스 픽셀의 알파 255 → 약 102
  ③ render_layer_one(썸네일)   : 같음
  ④ compose(최종 mp4)          : 0%에서 분홍이던 자리가 60%에선 밑바탕(템플릿 어두운 면)과 섞여 R이 약 0.4배
"""
import sys, pathlib, shutil, statistics
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
timeline = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
             'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}}
            for i, c in enumerate(['주부들도 감탄한 천재 아이디어', '이건 바로 핑거 찹스틱'])]
TEXT = {'channel': '숏템메이커', 'hook1': '주부들도 감탄한', 'hook2': '천재 아이디어', 'bodyTitle': '주부들도 감탄한 천재 아이디어?'}
HEAD = {'text': '주부들도 감탄한\n천재 아이디어'}
def snap(clear):
    cap = {'placement': 'title', 'h': 12, 'background': '#ff2266', 'bgUser': True, 'boxClear': clear}
    return scene_style.validate_snapshot({'version': 1, 'mode': 'story', 'presetId': 't11', 'sceneIndex': 1, 'frameKind': 'body', 'text': TEXT,
                                          'captionLayouts': {f't11:story:{i}:caption': dict(cap) for i in range(2)}})
def pink_alpha(png):   # 박스색(#ff2266)인 픽셀들의 알파 중앙값과 개수
    im = Image.open(png).convert('RGBA'); w, h = im.size; al = []
    for y in range(0, h, 4):
        for x in range(0, w, 8):
            r, g, b, a = im.getpixel((x, y))
            if a > 20 and r > 230 and 20 < g < 50 and 85 < b < 120: al.append(a)
    return (int(statistics.median(al)) if al else 0), len(al)
res = {}
for clear in (0, 60):
    d = out / f'c{clear}'; s = snap(clear)
    scene_style.render_layers(timeline, s, d / 'layers', HEAD, 'cbqa')
    pngs = sorted((d / 'layers').rglob('*.png'))
    one = pathlib.Path(scene_style.render_layer_one(timeline, s, d / 'thumb', 1, HEAD, 'cbqa'))
    final = d / 'final.mp4'; scene_style.compose(str(src), timeline, s, str(final), d / 'cw', HEAD)
    frame = d / 'f.png'; va._run_ffmpeg(['ffmpeg', '-y', '-ss', '1.5', '-i', str(final), '-frames:v', '1', str(frame)])
    im = Image.open(frame).convert('RGB'); W, H = im.size
    if clear == 0: spots = [(x, y) for y in range(0, H, 4) for x in range(0, W, 8) if (lambda c: c[0] > 220 and c[1] < 70 and 70 < c[2] < 140)(im.getpixel((x, y)))]
    red = statistics.median(im.getpixel(q)[0] for q in spots) if spots else 0      # 0%에서 분홍이던 자리들의 R
    res[clear] = {'layer': pink_alpha(pngs[1]) if len(pngs) > 1 else (0, 0), 'thumb': pink_alpha(one), 'spots': len(spots), 'red': red}
    print(f'  투명도 {clear}%: 레이어 {res[clear]["layer"]} / 썸네일 {res[clear]["thumb"]} / mp4 박스 자리 {len(spots)}곳 R 중앙값 {red}')
a0, a6 = res[0], res[60]
need(a0['layer'][1] > 200 and a0['layer'][0] > 240, f'② 0%: 렌더 레이어에 박스가 불투명하게 찍힌다 {a0["layer"]}')
need(a6['layer'][1] > 200 and 90 <= a6['layer'][0] <= 115, f'② 60%: 렌더 레이어 박스 알파가 약 102 {a6["layer"]}')
need(a0['thumb'][0] > 240 and 90 <= a6['thumb'][0] <= 115, f'③ 썸네일 한 장도 같다 {a0["thumb"]} → {a6["thumb"]}')
need(a0['spots'] > 200 and a0['red'] > 240 and 85 <= a6['red'] <= 140, f'④ 최종 mp4: 박스 자리 R {a0["red"]} → {a6["red"]} (밑바탕과 섞임)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건'); sys.exit(1 if fails else 0)
