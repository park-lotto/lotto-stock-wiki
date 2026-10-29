# -*- coding: utf-8 -*-
"""구간 확대 접촉 시트(rangesheet) — t0~t1 을 step 초 간격으로, 시각 라벨 붙여 cols 칸 격자(사람 눈 판독용, 측정 아님).

어디서 왔나: 06 홈디자인노트 워커(관제 263, 10-25)의 세션 임시 폴더 도구 sheet.py 를 그대로 옮김(알고리즘 바꾸지 않음).
다른 시트와 무엇이 다른가: kal_analyze frames 의 시트(starpickroom sheets.py)는 **영상 전체를 고정 fps** 로, strips 는 '글자 바뀌는 지점 ±0.3초'.
            이 도구는 **사람이 고른 아무 구간**을 1프레임(0.033초) 간격까지 촘촘히 — 전환·등장 애니메이션 확대 판독용.
입력: mp4 · 출력 jpg · t0 t1 step · [cols 10] [scale 0.2] [y0 y1 자르기]
출력: jpg 한 장. 함수는 {tiles, shape} 를 돌려준다.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/rangesheet.py <mp4> <out.jpg> <t0> <t1> <step> [cols] [scale] [y0 y1]
"""
from __future__ import annotations

import sys

import cv2
import numpy as np


def rangesheet(mp4: str, out: str, t0: float, t1: float, step: float, cols: int = 10, sc: float = 0.2,
               y0: int = 0, y1: int | None = None) -> dict:
    cap = cv2.VideoCapture(mp4)
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ts = []
    t = t0
    while t <= t1 + 1e-6:
        ts.append(t)
        t += step
    want = {min(n - 1, int(round(x * fps))): x for x in ts}
    tiles = []
    i = 0
    maxf = max(want)
    while i <= maxf:
        ok, f = cap.read()
        if not ok:
            break
        if i in want:
            f = f[y0:y1]
            f = cv2.resize(f, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
            cv2.rectangle(f, (0, 0), (f.shape[1], 16), (0, 0, 0), -1)
            cv2.putText(f, f"{want[i]:.2f}", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
            tiles.append(f)
        i += 1
    cap.release()
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    S = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, tl in enumerate(tiles):
        S[(k // cols) * h:(k // cols + 1) * h, (k % cols) * w:(k % cols + 1) * w] = tl
    cv2.imencode(".jpg", S, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(out)
    return {"tiles": len(tiles), "shape": S.shape}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 5:
        print(__doc__)
        return 2
    mp4, out, t0, t1, step = a[0], a[1], float(a[2]), float(a[3]), float(a[4])
    cols = int(a[5]) if len(a) > 5 else 10
    sc = float(a[6]) if len(a) > 6 else 0.2
    y0, y1 = (int(a[7]), int(a[8])) if len(a) > 8 else (0, None)
    r = rangesheet(mp4, out, t0, t1, step, cols, sc, y0, y1)
    print(out, r["tiles"], r["shape"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
