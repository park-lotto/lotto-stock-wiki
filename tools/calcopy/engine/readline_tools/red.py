# -*- coding: utf-8 -*-
"""빨간 표시(손그림 원·화살표) 프레임별 추적(red).

어디서 왔나: 06 이븐쇼핑 워커(관제 263, 10-25) `channel/evenshopping/_kal/측정도구/red.py` 를 옮김(알고리즘 바꾸지 않음).
            박혀 있던 원본 경로·창 자르기(y 590, 높이 1220)는 인자·프로필(`profiles/<slug>.json` 의 "red")로 뺐다.
무엇을 재나: t0~t1 을 30fps 로, 창(1080 x crop_h, 위 crop_y)을 1/4 로 줄여 빨강(H<8 또는 >172, S>150, V>120) 픽셀 수·상자(원본 좌표, 4px 단위),
            연하늘(H 85~110, S<90, V>200) 비율·흰(최소 채널 >225) 비율 — 증거 카드(흰·연하늘 바탕) 위에 빨간 표시가 그려지는 순간을 찾는다.
입력: mp4 · t0 t1 · [--crop-y 590 --crop-h 1220] 또는 --profile
출력: 표준출력 줄 `t 빨강칸수 (x0,y0,x1,y1)|None 연하늘비 흰비` (옛 꼴 그대로) · 함수는 dict 목록

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/red.py <mp4> <t0> <t1> [--profile profiles/evenshopping.json]
    (옛 꼴: --src-dir C:/숏템_칼카피/evenshopping/src <id> <t0> <t1>)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

DEFAULTS = {"crop_y": 0, "crop_h": 1920}


def red_track(mp4: str, t0: float, t1: float, crop_y: int = 0, crop_h: int = 1920, fps: int = 30) -> list[dict]:
    W, H = 270, crop_h // 4
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(t0), "-to", str(t1), "-i", mp4,
                          "-vf", f"fps={fps},crop=1080:{crop_h}:0:{crop_y},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    i = 0
    out = []
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        f = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        red = ((hsv[..., 0] < 8) | (hsv[..., 0] > 172)) & (hsv[..., 1] > 150) & (hsv[..., 2] > 120)
        ys, xs = np.where(red)
        lightblue = ((hsv[..., 0] > 85) & (hsv[..., 0] < 110) & (hsv[..., 1] < 90) & (hsv[..., 2] > 200)).mean()
        white = ((f.min(2)) > 225).mean()
        out.append({"t": round(t0 + i / fps, 3), "red": int(red.sum()),
                    "box": (int(xs.min() * 4), int(ys.min() * 4 + crop_y), int(xs.max() * 4), int(ys.max() * 4 + crop_y)) if len(xs) > 20 else None,
                    "lightblue": round(float(lightblue), 2), "white": round(float(white), 2)})
        i += 1
    p.wait()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mp4", help="mp4 경로 또는 (--src-dir 와 함께) 영상 id")
    ap.add_argument("t0", type=float)
    ap.add_argument("t1", type=float)
    ap.add_argument("--src-dir")
    ap.add_argument("--profile")
    ap.add_argument("--crop-y", type=int)
    ap.add_argument("--crop-h", type=int)
    A = ap.parse_args(argv)
    P = dict(DEFAULTS)
    if A.profile:
        P.update(json.loads(Path(A.profile).read_text(encoding="utf-8")).get("red") or {})
    if A.crop_y is not None:
        P["crop_y"] = A.crop_y
    if A.crop_h is not None:
        P["crop_h"] = A.crop_h
    mp4 = str(Path(A.src_dir) / f"{A.mp4}.mp4") if A.src_dir else A.mp4
    for r in red_track(mp4, A.t0, A.t1, P["crop_y"], P["crop_h"]):
        print(r["t"], r["red"], r["box"], r["lightblue"], r["white"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
