# 사용: grid.py mp4 t0 t1 step y0 y1 out.jpg [cols=4] [scale=0.5]
# 띠(y0~y1)를 step 초마다 잘라 cols 열 격자로 — 0.1초 띠를 한 장에 많이 보기 위한 판독 보조(그림만 만든다)
import sys, cv2, numpy as np
mp4, t0, t1, st, y0, y1, out = sys.argv[1:8]
cols = int(sys.argv[8]) if len(sys.argv) > 8 else 4
sc = float(sys.argv[9]) if len(sys.argv) > 9 else 0.5
t0, t1, st, y0, y1 = float(t0), float(t1), float(st), int(y0), int(y1)
cap = cv2.VideoCapture(mp4); fps = cap.get(cv2.CAP_PROP_FPS)
cap.set(cv2.CAP_PROP_POS_MSEC, max(0, t0 - 0.3) * 1000)
tiles = []; want = t0
while want <= t1 + 1e-6:
    ok, f = cap.read()
    if not ok: break
    t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 - 1 / fps
    if t + 0.5 / fps >= want:
        c = cv2.resize(f[y0:y1].copy(), None, fx=sc, fy=sc)
        cv2.rectangle(c, (0, 0), (70, 24), (0, 0, 0), -1)
        cv2.putText(c, f"{want:.2f}" if st < 0.1 else f"{want:.1f}", (2, 19), 0, 0.6, (0, 255, 255), 2)
        tiles.append(c); want = round(want + st, 4)
h, w = tiles[0].shape[:2]
while len(tiles) % cols: tiles.append(np.zeros_like(tiles[0]))
rows = [np.hstack(tiles[i:i + cols] ) for i in range(0, len(tiles), cols)]
g = np.vstack(rows)
cv2.imwrite(out, g, [cv2.IMWRITE_JPEG_QUALITY, 88]); print(len(tiles), g.shape)
