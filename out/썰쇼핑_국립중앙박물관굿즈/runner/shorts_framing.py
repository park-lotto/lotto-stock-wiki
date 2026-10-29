"""숏폼(린박스·명화관·웃긴버거·어랍숏) 원본 장면의 AGY 피사체 영수증 → 카메라 경로.

사장님 결정(2026-10-07): 숏폼 4채널도 피사체를 구독 AGY 가 판독하고(②), 135~190% 로 확대하며(③), 확대한 창의 가로·세로
가운데에 피사체를 둔다(④). 판독·산수는 롱폼과 같은 부품이다 — subject_agy(판독 → 지킬 영역) 와 longform_reframe
(지킬 영역 → 배율·창 위치). 다른 것은 창 비율(영상 창 가로:세로)과 «원본에서 쓸 영역»(content_rect · 레터박스·하드섭 제외) 뿐이다.

서버가 rinbox_camera.source_shots[장면] = {'focus': {path, sha256, focus_key}} 로 영수증을 가리키면, 렌더 직전(render_context)에
여기서 [원본 초, cx, cy] 경로와 창 크기(crop = 원본 대비 비율)로 푼다. 영수증이 바뀌었거나 다른 원본·다른 창 비율이면 멈춘다
(가운데를 짐작하지 않는다 — longform_reframe 과 같은 규칙).
"""
import json
import math
from pathlib import Path


def aspect_of(video):
    """영상 창 {width, height} → 기약 정수비 (가로, 세로)."""
    w, h = int(video['width']), int(video['height'])
    if w <= 0 or h <= 0:
        raise ValueError('video window must have a positive size')
    g = math.gcd(w, h)
    return (w // g, h // g)


def _digest(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _decimate(points):
    """같은 직선 위 가운데 점을 뺀다(렌더 식이 선형 보간이라 결과는 같다)."""
    out = []
    for p in points:
        out.append(p)
        while len(out) >= 3:
            a, b, d = out[-3:]
            if any(abs(b[k] - (a[k] + (d[k] - a[k]) * (b[0] - a[0]) / (d[0] - a[0]))) > 1e-9 for k in (1, 2)):
                break
            out.pop(-2)
    return out


#: 창 크기 비율이 계산 오차로 1 을 아주 조금 넘는 것(배율 1.0 = 쓸 영역 전체 · 988.0000000000002/988)만 1 로 본다.
#: 2026-10-08 실측: 런닝맨 편 장면 30개 중 15개가 세로 1.0000000000000002 로 나와 렌더 검사(film_continuity.project_camera
#: «(0,1] 안») 가 렌더 전체를 막았다 — 린박스·명화관·웃긴버거·어랍숏 모두 같은 길이다. 이 폭보다 크게 넘으면 그대로 두어 검사가 막는다.
_FRACTION_EPS = 1e-9


def _fraction(value):
    return 1.0 if 1.0 < value <= 1.0 + _FRACTION_EPS else value


#: 박힌 자막 상자를 쓸 영역 밖으로 미는 조건 — 쓸 영역 가로의 BURN_MIN_W 이상인 띠 모양 글자가 위·아래 BURN_EDGE 안에 있을 때만.
#: 민 뒤에도 쓸 영역 세로가 BURN_KEEP 이상 남고 주인공 상자를 자르지 않을 때만 민다(그 밖에는 그대로 — 주인공이 먼저다).
BURN_MIN_W, BURN_EDGE, BURN_KEEP = .25, .3, .6


def burned_in_bounds(bounds, receipt, size):
    """판독이 적은 박힌 자막·로고(selection_evidence.burned_in_xyxy_norm)를 쓸 영역 [l, t, r, b] 의 위·아래 가장자리 밖으로."""
    fs = receipt.get('framing_subject') or {}
    boxes = (fs.get('selection_evidence') or {}).get('burned_in_xyxy_norm') or []
    sw, sh = size
    left, top, right, bottom = bounds
    height = bottom - top
    track = [p['bbox'] for p in fs.get('track') or []]
    keep_top = min((y for _, y, _, _ in track), default=bottom)
    keep_bottom = max((y + h for _, y, _, h in track), default=top)
    new_top, new_bottom = top, bottom
    for x1, y1, x2, y2 in boxes:
        x1, x2, y1, y2 = x1 * sw, x2 * sw, y1 * sh, y2 * sh
        if min(x2, right) - max(x1, left) < BURN_MIN_W * (right - left):
            continue
        if y2 <= top + BURN_EDGE * height and y1 >= top - 1:
            new_top = max(new_top, math.ceil(y2))
        elif y1 >= bottom - BURN_EDGE * height and y2 <= bottom + 1:
            new_bottom = min(new_bottom, math.floor(y1))
    if new_top > keep_top or new_bottom < keep_bottom or new_bottom - new_top < BURN_KEEP * height:
        return list(bounds)
    return [left, new_top, right, new_bottom]


def resolve(trajectories, source_sha256, size, content, video):
    """{장면: {'focus': {...}}} 를 {장면: {'points': [[초, cx, cy], …], 'crop': [가로비, 세로비]}} 로. 다른 장면은 그대로."""
    from longform_reframe import from_focus_receipt
    sw, sh = size
    bounds = [content['x'], content['y'], content['x'] + content['width'], content['y'] + content['height']]
    aspect = aspect_of(video)
    out = {}
    for sid, traj in trajectories.items():
        focus = traj.get('focus') if isinstance(traj, dict) else None
        if focus is None:
            out[sid] = traj
            continue
        if (not isinstance(focus, dict) or set(focus) - {'path', 'sha256', 'focus_key', 'source_identity'}
                or not all(isinstance(focus.get(k), str) for k in ('path', 'sha256', 'focus_key'))):
            raise ValueError(f'{sid}: subject focus must name the receipt path, sha256 and focus_key')
        path = Path(focus['path'])
        if not path.is_file() or _digest(path) != focus['sha256']:
            raise ValueError(f'{sid}: subject receipt is missing or changed since the AGY reading; measure again')
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if receipt.get('focus_key') != focus['focus_key']:
            raise ValueError(f'{sid}: subject receipt belongs to another shot')
        scene = receipt.get('scene_evidence') or {}
        origin, frames, fps = scene.get('start'), scene.get('nframes'), scene.get('fps')
        plan = from_focus_receipt(receipt, source_sha256, origin, frames, fps, [sw, sh], str(sid),
                                  bounds=burned_in_bounds(bounds, receipt, size), aspect=aspect)
        rows = plan['samples']
        cw, ch = rows[0]['crop'][2], rows[0]['crop'][3]
        points = _decimate([[float(origin) + i / fps, (r['crop'][0] + cw / 2) / sw, (r['crop'][1] + ch / 2) / sh]
                            for i, r in enumerate(rows)])
        out[sid] = {'points': points, 'crop': [_fraction(cw / sw), _fraction(ch / sh)],
                    'focus': dict(focus), 'zoom': plan['zoom'], 'fallback': plan.get('fallback')}
    # 한두 프레임짜리 원본 장면(서버 volcano_shorts_agy.flash_aliases): 따로 판독하지 않고 이웃 장면과 같은 창을 그 장면 시각에 둔다.
    #   뒤 장면의 머리(side 'next')면 그 장면의 첫 점, 앞 장면의 꼬리('prev')면 마지막 점 — 창 크기도 같다(렌더에서 창이 튀지 않는다).
    for sid, traj in trajectories.items():
        if not (isinstance(traj, dict) and 'same_as' in traj):
            continue
        owner = out.get(traj['same_as'])
        side = traj.get('side')
        if (not isinstance(owner, dict) or 'focus' not in owner or side not in ('next', 'prev') or set(traj) != {'same_as', 'at', 'side'}
                or not isinstance(traj['at'], (int, float)) or isinstance(traj['at'], bool)):
            raise ValueError(f'{sid}: a flash shot must name a read neighbour (same_as), its own start (at) and side next|prev')
        x, y = owner['points'][0 if side == 'next' else -1][1:]
        out[sid] = {'points': [[float(traj['at']), x, y]], 'crop': list(owner['crop']), 'same_as': traj['same_as'],
                    'zoom': owner['zoom'], 'fallback': owner.get('fallback')}
    return out
