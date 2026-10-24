# -*- coding: utf-8 -*-
"""컷 검출(cutdet) — 창 안 매 프레임 밝기차·히스토그램차로 컷·전환 종류·샷별 움직임.

어디서 왔나: 06 잇템로그 워커(관제 263, 10-24)의 세션 임시 폴더 도구 cutdet.py 를 그대로 옮김(알고리즘 바꾸지 않음).
무엇을 재나: 창[y0,y1)을 360폭 회색으로 줄여 프레임차 > max(12, 3.5×이웃 중앙값) 또는 히스토그램차 > 0.35 = 컷(2프레임 안 붙은 것 합침).
            컷 앞뒤 ±4프레임 최소 밝기 <10 = black, 앞뒤보다 +50 밝으면 flash, 선명도(라플라시안)가 앞뒤 45% 미만 3프레임↑ = zoomblur, 나머지 cut.
            샷마다 첫·끝 프레임 평균차 chg(움직임 신호 — build_lr 은 6 미만을 still 로 본다).
입력: mp4 · 창 y0 y1 (줄판독 layout.window 의 세로, 예: 잇템로그 486 1920)
출력(json): {n(프레임 수), cuts:[{t, t_end, kind, diff, blurfr}], shots:[{t0, t1, chg}]}

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/cutdet.py <mp4> <y0> <y1> <out.json>
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np


def cutdet(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080) -> dict:
    H = y1 - y0
    w, h = 360, int(H / 3)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"crop={width}:{H}:0:{y0},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = len(raw) // (w * h)
    F = np.frombuffer(raw, np.uint8)[:n * w * h].reshape(n, h, w).astype(np.float32)
    mean = F.mean((1, 2))
    sharp = np.array([cv2.Laplacian(f[:int(h * 0.55)], cv2.CV_32F).var() for f in F])
    diff = np.r_[0, np.abs(F[1:] - F[:-1]).mean((1, 2))]
    hist = [cv2.calcHist([f.astype(np.uint8)], [0], None, [32], [0, 256]).ravel() for f in F]
    hist = [x / x.sum() for x in hist]
    hd = np.r_[0, [0.5 * np.abs(hist[i] - hist[i - 1]).sum() for i in range(1, n)]]
    med = np.array([np.median(diff[max(0, i - 15):i + 15]) for i in range(n)])
    cuts = [i for i in range(1, n) if (diff[i] > max(12, 3.5 * med[i]) or hd[i] > 0.35)]
    cm = []
    for c in cuts:
        if cm and c - cm[-1][-1] <= 2:
            cm[-1].append(c)
        else:
            cm.append([c])
    res = []
    for g in cm:
        a, b = g[0], g[-1]
        lo = max(0, a - 4)
        hi = min(n - 1, b + 4)
        kind = "cut"
        lowblur = 0
        if mean[lo:hi + 1].min() < 10:
            kind = "black"
        elif mean[lo:hi + 1].max() > max(mean[max(0, a - 8)], mean[min(n - 1, b + 8)]) + 50:
            kind = "flash"
        else:
            pre = np.median(sharp[max(0, a - 10):max(1, a - 4)])
            post = np.median(sharp[min(n - 1, b + 5):min(n, b + 11)])
            win = sharp[max(0, a - 3):min(n, b + 3)]
            lowblur = int((win < 0.45 * min(pre, post)).sum())
            if lowblur >= 3:
                kind = "zoomblur"
        res.append({"t": round(a / fps, 3), "t_end": round(b / fps, 3), "kind": kind, "diff": round(float(diff[a:b + 1].max()), 1),
                    "blurfr": lowblur if kind not in ("black", "flash") else 0})
    bounds = [0] + [int(r["t"] * fps) for r in res] + [n]
    shots = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1] - 1
        if b - a < 3:
            shots.append({"t0": round(a / fps, 3), "t1": round((b + 1) / fps, 3), "motion": "still?", "chg": 0})
            continue
        A = F[a + 1]
        B = F[b - 1]
        chg = float(np.abs(A - B).mean())
        shots.append({"t0": round(a / fps, 3), "t1": round((b + 1) / fps, 3), "chg": round(chg, 1)})
    return {"n": n, "cuts": res, "shots": shots}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 4:
        print(__doc__)
        return 2
    mp4, y0, y1, out = a[0], int(a[1]), int(a[2]), a[3]
    d = cutdet(mp4, y0, y1)
    json.dump(d, open(out, "w"), indent=0)
    for r in d["cuts"]:
        print(r)
    print("shots", len(d["shots"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
