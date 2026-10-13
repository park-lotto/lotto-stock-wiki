# -*- coding: utf-8 -*-
"""녹화본에서 계정 이름(템플릿) 찾아 흐리게. 사용: py blur_accounts.py <in.mp4> <out.mp4> <ref.png> x0,y0,x1,y1 [x0,y0,x1,y1 ...]
ref.png 의 사각형들이 지울 글자 모양(템플릿). 매 프레임 여러 크기(0.6~1.1배)로 찾아 맞는 곳을 흐린다."""
import sys, cv2, numpy as np
src, dst, ref = sys.argv[1:4]
R = cv2.imread(ref, cv2.IMREAD_GRAYSCALE)
tpls = []
for b in sys.argv[4:]:
    x0, y0, x1, y1 = map(int, b.split(','))
    t = R[y0:y1, x0:x1]
    for s in (0.66, 0.7, 0.74, 0.77, 0.8, 0.84, 0.9, 0.95, 1.0, 1.05):
        tt = cv2.resize(t, None, fx=s, fy=s)
        tpls.append(tt)
cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS); w = int(cap.get(3)); h = int(cap.get(4))
out = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
n = hits = 0
while True:
    ok, fr = cap.read()
    if not ok: break
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    boxes = []
    for t in tpls:
        th, tw = t.shape
        if th >= h or tw >= w: continue
        r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(r >= 0.66)
        for x, y in zip(xs, ys): boxes.append((x, y, tw, th))
    for x, y, tw, th in boxes:
        x0, y0 = max(0, x - 4), max(0, y - 4); x1, y1 = min(w, x + tw + 4), min(h, y + th + 4)
        fr[y0:y1, x0:x1] = cv2.GaussianBlur(fr[y0:y1, x0:x1], (0, 0), 9)
    hits += bool(boxes); n += 1
    out.write(fr)
out.release()
print('frames', n, 'with_blur', hits)
