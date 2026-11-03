# 원작 presets/ink_explainer/tools/trace.py 복사본 — SHOTLIST §4-1 네 군데만 바꿈
# (S=1024 / 이름 인자 / 215 이상 흰색 / ink<160 / 획≥10점), 출력 hero_strokes.js
# 쓰기: py trace_hero.py g_f_hope g_m_tired ...   (이름별 문턱 바꾸기: g_x:120)
# 눈 위치·머리 높이(ex,ey,hpx)는 hero_anchor.json(사람이 그림을 보고 잰 값)을 읽어 같이 싣는다.
import cv2, numpy as np, json, sys, os
from skimage.morphology import skeletonize
import numpy as _np, cv2 as _cv2
def _imread(p, flag=_cv2.IMREAD_COLOR): return _cv2.imdecode(_np.fromfile(p, _np.uint8), flag)
def _imwrite(p, im): _cv2.imencode(".png", im)[1].tofile(p)
HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
out = {}
anchor = json.load(open(os.path.join(HERE, "hero_anchor.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "hero_anchor.json")) else {}
for arg in sys.argv[1:]:
    name, thr = (arg.split(":") + ["160"])[:2]
    g = _imread(os.path.join(HERE, name + ".png"), cv2.IMREAD_GRAYSCALE)
    g = cv2.resize(g, (S, S), interpolation=cv2.INTER_AREA)
    g[g >= 215] = 255
    ink = g < int(thr)
    sk = skeletonize(ink)
    ys, xs = np.nonzero(sk)
    pts = set(zip(xs.tolist(), ys.tolist()))
    N = [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]
    deg = lambda p: sum((p[0]+dx, p[1]+dy) in pts for dx, dy in N)
    strokes = []
    left = set(pts)
    def walk(p):
        line = [p]; left.discard(p)
        while True:
            nx = [(p[0]+dx, p[1]+dy) for dx, dy in N if (p[0]+dx, p[1]+dy) in left]
            if not nx: break
            p = nx[0]; left.discard(p); line.append(p)
        return line
    ends = sorted([p for p in pts if deg(p) == 1], key=lambda p: (p[1], p[0]))
    for e in ends:
        if e in left: strokes.append(walk(e))
    while left:
        strokes.append(walk(min(left, key=lambda p: (p[1], p[0]))))
    res = []
    for s in strokes:
        if len(s) < 10: continue
        a = cv2.approxPolyDP(np.array(s, np.int32).reshape(-1, 1, 2), 0.8, False).reshape(-1, 2)
        res.append(a.tolist())
    order, cur = [], (0, 0)
    pool = res[:]
    while pool:
        i = min(range(len(pool)), key=lambda k: min((pool[k][0][0]-cur[0])**2 + (pool[k][0][1]-cur[1])**2, (pool[k][-1][0]-cur[0])**2 + (pool[k][-1][1]-cur[1])**2))
        s = pool.pop(i)
        if (s[-1][0]-cur[0])**2 + (s[-1][1]-cur[1])**2 < (s[0][0]-cur[0])**2 + (s[0][1]-cur[1])**2: s = s[::-1]
        order.append(s); cur = tuple(s[-1])
    ent = {"S": S, "thr": int(thr), "paths": ["M" + " L".join(f"{x} {y}" for x, y in s) for s in order]}
    ent.update(anchor.get(name, {}))
    out[name] = ent
    print(name, len(order), sum(len(s) for s in order), "anchor" if name in anchor else "NO-ANCHOR")
open(os.path.join(HERE, "hero_strokes.js"), "w", encoding="utf-8").write("window.HERO_STROKES=" + json.dumps(out) + ";")
