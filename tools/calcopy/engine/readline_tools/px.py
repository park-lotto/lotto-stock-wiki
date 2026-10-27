# -*- coding: utf-8 -*-
"""픽셀 실측(px) — 한 시각 프레임의 자막 채움색·글자 상자.

어디서 왔나: 06 워커(관제 263, 10-24~25)의 세션 임시 폴더 도구 두 벌을 한 파일로 옮김(알고리즘 바꾸지 않음).
  clusters = 잇템로그 워커 px.py : '검정 외곽 옆 밝은 채움'(V>170 & 검정 V<45 9x9 팽창) 픽셀을 k-means K묶음 → 묶음별 hex·칸 수·x/y 범위(2~98%).
             색 글자(빨강·노랑 채움 + 검정 외곽) 채널용.
  box      = 홈디자인노트 워커 px.py : 흰 글자(V>215 & S<60) 연결요소(높이 8~130·폭<300·넓이≥15) → 잉크 상자·채움 hex·
             테두리 고리(3~7px) hex·배경(13~25px) hex·글자 높이. 흰 채움 + 색 외곽 채널용.
입력: mp4 · 시각 t(초) · 띠 y0 y1
출력: 표준출력 줄(옛 도구와 같은 꼴) + 함수는 dict 를 돌려준다.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/px.py <mp4> <t> <y0> <y1> [K]            # clusters(옛 꼴 그대로)
    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/px.py box <mp4> <y0> <y1> <t1> [t2 ...]
"""
from __future__ import annotations

import sys

import cv2
import numpy as np


def _hx_bgr(c) -> str:
    return "#%02X%02X%02X" % (int(c[2]), int(c[1]), int(c[0]))


def _frame(mp4: str, t: float):
    cap = cv2.VideoCapture(mp4)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def fill_clusters(mp4: str, t: float, y0: int, y1: int, K: int = 3, frame=None) -> dict | None:
    f = _frame(mp4, t) if frame is None else frame
    b = f[y0:y1]
    hsv = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    dark = (hsv[..., 2] < 45).astype(np.uint8)
    m = (hsv[..., 2] > 170) & (cv2.dilate(dark, np.ones((9, 9), np.uint8)) > 0)
    ys, xs = np.where(m)
    px = b[m].astype(np.float32)
    if len(px) < 20:
        return None
    _, lab, cen = cv2.kmeans(px, K, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1), 3, cv2.KMEANS_PP_CENTERS)
    groups = []
    for k in range(K):
        s = lab.ravel() == k
        c = np.median(px[s], 0).astype(int)
        groups.append({"hex": _hx_bgr(c), "n": int(s.sum()),
                       "x": [int(np.percentile(xs[s], 2)), int(np.percentile(xs[s], 98))],
                       "y": [y0 + int(np.percentile(ys[s], 2)), y0 + int(np.percentile(ys[s], 98))]})
    return {"t": t, "groups": groups, "ink_y": [int(y0 + ys.min()), int(y0 + ys.max())], "ink_x": [int(xs.min()), int(xs.max())]}


def ink_box(mp4: str, t: float, b0: int, b1: int, cap=None) -> dict | None:
    if cap is None:
        f = _frame(mp4, t)
    else:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
    band = f[b0:b1]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 2] > 215) & (hsv[..., 1] < 60)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if 8 <= h <= 130 and a >= 15 and w < 300:
            keep[lab == k] = 1
    ys, xs = np.nonzero(keep)
    if len(ys) == 0:
        return None
    rowsum = keep.sum(1)
    rr = np.nonzero(rowsum > 3)[0]
    fill = np.median(band[keep > 0], axis=0)
    ring = cv2.dilate(keep, np.ones((7, 7), np.uint8)) - cv2.dilate(keep, np.ones((3, 3), np.uint8))
    ringc = np.median(band[ring > 0], axis=0)
    far = cv2.dilate(keep, np.ones((25, 25), np.uint8)) - cv2.dilate(keep, np.ones((13, 13), np.uint8))
    farc = np.median(band[far > 0], axis=0)
    return {"t": t, "x": [int(xs.min()), int(xs.max())], "y": [int(b0 + rr.min()), int(b0 + rr.max())], "h": int(rr.max() - rr.min() + 1),
            "cx": int((xs.min() + xs.max()) // 2), "fill": _hx_bgr(fill), "ring": _hx_bgr(ringc), "bg": _hx_bgr(farc)}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a and a[0] == "box":
        if len(a) < 5:
            print(__doc__)
            return 2
        mp4, b0, b1 = a[1], int(a[2]), int(a[3])
        cap = cv2.VideoCapture(mp4)
        for t in map(float, a[4:]):
            r = ink_box(mp4, t, b0, b1, cap=cap)
            if r is None:
                print(t, "잉크 없음")
                continue
            print(f"t={t} x[{r['x'][0]},{r['x'][1]}] y[{r['y'][0]},{r['y'][1]}] h={r['h']} cx={r['cx']} fill={r['fill']} ring3-7px={r['ring']} bg13-25px={r['bg']}")
        return 0
    if a and a[0] == "clusters":
        a = a[1:]
    if len(a) < 4:
        print(__doc__)
        return 2
    mp4, t, y0, y1 = a[0], float(a[1]), int(a[2]), int(a[3])
    K = int(a[4]) if len(a) > 4 else 3
    r = fill_clusters(mp4, t, y0, y1, K)
    if r is None:
        print("no ink")
        return 0
    for g in r["groups"]:
        print(g["hex"], g["n"], "x", g["x"][0], g["x"][1], "y", g["y"][0], g["y"][1])
    print("ink y", r["ink_y"][0], r["ink_y"][1], "x", r["ink_x"][0], r["ink_x"][1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
