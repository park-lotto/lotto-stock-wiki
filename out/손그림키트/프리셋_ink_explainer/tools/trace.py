import cv2, numpy as np, json, sys
from skimage.morphology import skeletonize
S = 700
out = {}
for name in ["i_think", "i_flow", "i_folder", "i_empty", "i_clock", "i_man"]:
    g = cv2.imread(name + ".png", cv2.IMREAD_GRAYSCALE)
    g = cv2.resize(g, (S, S), interpolation=cv2.INTER_AREA)
    ink = g < 140
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
        if len(s) < 6: continue
        a = cv2.approxPolyDP(np.array(s, np.int32).reshape(-1, 1, 2), 0.8, False).reshape(-1, 2)
        res.append(a.tolist())
    # human-ish order: chain nearest stroke start, beginning top-left
    order, cur = [], (0, 0)
    pool = res[:]
    while pool:
        i = min(range(len(pool)), key=lambda k: min((pool[k][0][0]-cur[0])**2 + (pool[k][0][1]-cur[1])**2, (pool[k][-1][0]-cur[0])**2 + (pool[k][-1][1]-cur[1])**2) + pool[k][0][1] * 0.0)
        s = pool.pop(i)
        if (s[-1][0]-cur[0])**2 + (s[-1][1]-cur[1])**2 < (s[0][0]-cur[0])**2 + (s[0][1]-cur[1])**2: s = s[::-1]
        order.append(s); cur = tuple(s[-1])
    out[name] = ["M" + " L".join(f"{x} {y}" for x, y in s) for s in order]
    print(name, len(order), sum(len(s) for s in order))
open("strokes.js", "w", encoding="utf-8").write("window.STROKES=" + json.dumps(out) + ";")
