# -*- coding: utf-8 -*-
"""자막 띠 분할(capseg) — 30fps 매 프레임 글자 잉크 마스크가 바뀌는 지점으로 자막 덩어리를 자른다.

어디서 왔나: 06 잇템로그 워커(관제 263, 10-24)의 세션 임시 폴더 도구 capseg.py 를 그대로 옮김(알고리즘 바꾸지 않음).
무엇을 재나: 띠[y0,y1) 안에서 '검정 외곽 옆 밝은 채움'(V>185 & 검정 V<45 를 9x9 팽창한 곳) 픽셀 = 글자 잉크.
            이웃 프레임 마스크 IoU 차 > 0.45 이고 잉크가 있으면 새 덩어리.
입력: mp4 · 띠 y0 y1 (예: 잇템로그 1150 1460)
출력(json 목록): [{t0, t1, n(프레임 수), ink(가운데 프레임 잉크 칸 수), hex(채움 중앙값 #RRGGBB), yr([y 위, y 아래] 원본 좌표, 4px 단위)}]

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/capseg.py <mp4> <y0> <y1> <out.json>
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np


def _diff(a, b):
    u = (a | b).sum()
    return 0 if u == 0 else 1 - (a & b).sum() / u


def capseg(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080) -> list[dict]:
    H = y1 - y0
    cmd = ["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"crop={width}:{H}:0:{y0}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (width * H * 3)
    F = np.frombuffer(raw, np.uint8)[:n * width * H * 3].reshape(n, H, width, 3)
    k = np.ones((9, 9), np.uint8)
    masks = []
    cols = []
    for f in F:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        v = hsv[..., 2]
        dark = (v < 45).astype(np.uint8)
        near = cv2.dilate(dark, k) > 0
        fill = ((v > 185) & near)
        m = fill.astype(np.uint8)
        masks.append(cv2.resize(m * 255, (270, max(1, H // 4)), interpolation=cv2.INTER_AREA) > 40)
        if m.sum() > 200:
            px = f[m > 0]
            cols.append(np.median(px, 0).astype(int).tolist())
        else:
            cols.append(None)
    cnt = [int(m.sum()) for m in masks]
    segs = []
    start = 0
    for i in range(1, n):
        d = _diff(masks[i], masks[i - 1])
        if d > 0.45 and (cnt[i] > 30 or cnt[i - 1] > 30):
            segs.append((start, i))
            start = i
    segs.append((start, n))
    res = []
    for a, b in segs:
        mid = (a + b) // 2
        c = [cc for cc in cols[a:b] if cc]
        col = np.median(np.array(c), 0).astype(int).tolist() if c else None
        hexs = "#%02X%02X%02X" % (col[2], col[1], col[0]) if col else None
        ys = np.where(masks[mid].any(1))[0]
        res.append({"t0": round(a / fps, 3), "t1": round(b / fps, 3), "n": b - a, "ink": cnt[mid], "hex": hexs,
                    "yr": [int(y0 + ys.min() * 4), int(y0 + ys.max() * 4)] if len(ys) else None})
    return res


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 4:
        print(__doc__)
        return 2
    mp4, y0, y1, out = a[0], int(a[1]), int(a[2]), a[3]
    res = capseg(mp4, y0, y1)
    json.dump(res, open(out, "w"), indent=0)
    for r in res:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
