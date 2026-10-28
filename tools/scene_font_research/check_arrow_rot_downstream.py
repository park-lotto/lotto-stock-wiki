"""편집기에서 돌린 화살표 각도가 **렌더 레이어·썸네일·최종 합성**까지 그대로 가나 (2026-10-03 관제 100).

왕해원님 제보 "화살표가 반대로 렌더에 적용": 편집기 손잡이는 ±180°까지 돌리는데 서버 검증
(`deco_frame._norm_masks`)이 ±45°로 잘라, 아래(90°)·왼쪽 아래(135°) 화살표가 전부 45°로 나갔다.

재는 법: 굵은 화살표(arrow_bold)는 0°에서 오른쪽을 가리킨다 — 빨간 점들의 긴 축을 구하고,
  그 축의 양쪽 중 옆으로 더 넓게 퍼진 쪽(삼각 머리)이 곧 가리키는 방향이다.
  ① 서버 검증이 각도를 그대로 돌려준다
  ② 렌더·캡컷용 레이어(render_layers)의 화살표 방향 = 넣은 각도
  ③ 썸네일용 한 장(render_layer_one)도 같다
  ④ 최종 합성(compose) mp4 프레임에서도 같다

  py tools/scene_font_research/check_arrow_rot_downstream.py <작업폴더>
"""
import sys, math, pathlib, shutil
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble as va
from PIL import Image
out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

ANGLES = (0, 45, 90, 135, 180, -90, -135)      # 오른쪽·오른아래·아래·왼아래·왼쪽·위·왼위
BOX = {'l': 35, 't': 40, 'w': 30, 'h': 16.875}  # 1080×1920에서 324×324 정사각
CX, CY = (BOX['l'] + BOX['w'] / 2) / 100, (BOX['t'] + BOX['h'] / 2) / 100
TOL = 12                                        # 허용 오차(도)

tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
src = out / 'src.mp4'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', f'color=c=blue:s=1080x1920:d={len(ANGLES)}', '-r', '30', '-pix_fmt', 'yuv420p', str(src)])
timeline = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': f'장면 {i}', 'caption_lines': [f'장면 {i}'], 'tts_path': str(tts), 'target_seconds': 1,
             'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}}
            for i in range(len(ANGLES))]
TEXT = {'channel': '숏템메이커', 'hook1': '화살표', 'hook2': '방향', 'bodyTitle': '화살표 방향'}
HEAD = {'text': '화살표\n방향'}
def arrow(rot):
    return {**BOX, 'kind': 'graphic', 'graphic': 'arrow_bold', 'color': '#FF3B30', 'rot': rot, 'motion': 'none',
            'shape': 'round', 'fx': 'solid', 'op': 100, 'soft': 30}
raw = {'version': 1, 'mode': 'story', 'plainCaption': 2, 'presetId': 'plain', 'sceneIndex': 0, 'frameKind': 'hook', 'text': TEXT,
       'effects': {str(i): {'zoom': 1, 'panX': 0, 'panY': 0, 'masks': [arrow(r)]} for i, r in enumerate(ANGLES)}}

# ① 서버 검증
snap = scene_style.validate_snapshot(raw)
got = [snap['effects'][str(i)]['masks'][0]['rot'] for i in range(len(ANGLES))]
need(got == list(ANGLES), f'① 서버 검증이 각도를 그대로 둔다 (넣음 {list(ANGLES)} → 나옴 {got})')

def direction(png, rgba=True):
    """빨간 화살표가 가리키는 방향(도, 화면 시계방향 +). 못 찾으면 None.
    긴 축(주축)을 구한 뒤, 그 축의 양쪽 중 **옆으로 더 넓게 퍼진 쪽**(=삼각 머리)이 가리키는 쪽이다."""
    im = Image.open(png).convert('RGBA' if rgba else 'RGB'); w, h = im.size
    x0, x1 = int(w * (CX - .22)), int(w * (CX + .22)); y0, y1 = int(h * (CY - .13)), int(h * (CY + .13))
    px = im.load(); pts = []
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            p = px[x, y]
            if p[0] > 180 and p[1] < 130 and p[2] < 130 and (not rgba or p[3] > 120):
                pts.append((x, y))
    n = len(pts)
    if n < 200:
        return None
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts) / n; syy = sum((p[1] - my) ** 2 for p in pts) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts) / n
    th = 0.5 * math.atan2(2 * sxy, sxx - syy)            # 주축 각도
    ux, uy = math.cos(th), math.sin(th)
    spread = {1: 0.0, -1: 0.0}
    for x, y in pts:
        t = (x - mx) * ux + (y - my) * uy; side = abs(-(x - mx) * uy + (y - my) * ux)
        k = 1 if t > 0 else -1
        spread[k] = max(spread[k], side)
    if abs(spread[1] - spread[-1]) < 4:
        return None                                      # 머리 쪽을 못 가린다 — 화살표가 아니다
    sign = 1 if spread[1] > spread[-1] else -1
    return math.degrees(math.atan2(sign * uy, sign * ux))
def same(a, b):
    return a is not None and abs((a - b + 180) % 360 - 180) <= TOL
def fmt(a):
    return '없음' if a is None else f'{a:.0f}°'

# ② 렌더·캡컷용 레이어
layers = scene_style.render_layers(timeline, snap, out / 'layers', HEAD, 'arrowqa')
need(len(layers) == len(ANGLES), f'② 레이어 {len(layers)}장 (장면 {len(ANGLES)}개)')
for i, r in enumerate(ANGLES[:len(layers)]):
    d = direction(out / 'layers' / layers[i]['file'])
    need(same(d, r), f'② 렌더 레이어: 넣은 각도 {r}° → 그림 속 화살표 {fmt(d)}')

# ③ 썸네일용 한 장
for i, r in ((2, 90), (3, 135)):
    one = pathlib.Path(scene_style.render_layer_one(timeline, snap, out / f'thumb{i}', i, HEAD, 'arrowqa'))
    d = direction(one) if one.exists() else None
    need(same(d, r), f'③ 썸네일 한 장: 넣은 각도 {r}° → 그림 속 화살표 {fmt(d)}')

# ④ 최종 합성 mp4
final = out / 'final.mp4'
scene_style.compose(str(src), timeline, snap, str(final), out / 'cw', HEAD)
need(final.exists() and final.stat().st_size > 1000, f'④ 최종 합성 mp4 생성 ({final.stat().st_size if final.exists() else 0} 바이트)')
if final.exists():
    for i, r in enumerate(ANGLES):
        frame = out / f'f{i}.png'; va._run_ffmpeg(['ffmpeg', '-y', '-ss', str(i + 0.5), '-i', str(final), '-frames:v', '1', str(frame)])
        d = direction(frame, rgba=False)
        need(same(d, r), f'④ 완성 영상 {i + 0.5}초: 넣은 각도 {r}° → 화면 속 화살표 {fmt(d)}')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
