# -*- coding: utf-8 -*-
"""샷 움직임(shotmotion) — 컷 정리(같은 그림 컷 버리기) + 샷마다 ORB 닮음변환으로 still/cam/zoom_in/zoom_out/pan.

어디서 왔나: 06 유머쇼쇼(재밌쇼) 워커(관제 263, 10-25) 세션 임시 폴더 motion.py 를 옮김(알고리즘 그대로, 경로는 인자로).
무엇을 재나:
  clean_cuts: cutdet 컷 중 diff<30 이고 0.25초 안에 다른 컷이 있으면 버림 · 0.2초 안 둘이면 앞 것만 ·
              컷 앞(−0.07초)·뒤(+0.1초) 프레임 ORB 닮음변환이 배율 1±0.03·인라이어 ≥40 이면 '같은 그림'(자막만 바뀐 것)으로 버림.
  shot_motion: 샷 첫(+0.07초)·끝(−0.1초) 프레임 평균차 d<4 still · ORB 닮음변환 배율 >1.025 zoom_in · <0.975 zoom_out ·
              이동 >25px pan · d<10 still · 나머지 cam.
cutdet --v2 의 motion 은 이 함수(shot_motion)를 부른다(주인 한 곳).

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/shotmotion.py <mp4> <cut.json> <y0> <y1> <out.json> [--same-band y0,y1]
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np


def _gray(cap, t, y0, y1):
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    return cv2.cvtColor(f[y0:y1], cv2.COLOR_BGR2GRAY) if ok else None


def clean_cuts(cap, cuts: list[dict], sy0: int, sy1: int) -> tuple[list[dict], list[dict]]:
    keep = []
    for c in cuts:
        near = [d for d in cuts if d is not c and abs(d["t"] - c["t"]) <= 0.25]
        if c["kind"] == "black" or c["diff"] >= 30 or not near:
            if c["diff"] < 30 and near:
                continue
            keep.append(c)
    k2 = []
    for c in keep:
        if k2 and c["t"] - k2[-1]["t"] < 0.2:
            continue
        k2.append(c)
    orb0 = cv2.ORB_create(2000)
    k3, dropped = [], []
    for c in k2:
        A = _gray(cap, c["t"] - 0.07, sy0, sy1)
        B = _gray(cap, c["t"] + 0.1, sy0, sy1)
        same = False
        if A is not None and B is not None:
            ka, da = orb0.detectAndCompute(A, None)
            kb, db = orb0.detectAndCompute(B, None)
            if da is not None and db is not None and len(ka) > 30 and len(kb) > 30:
                mt = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
                if len(mt) >= 20:
                    pa = np.float32([ka[m.queryIdx].pt for m in mt])
                    pb = np.float32([kb[m.trainIdx].pt for m in mt])
                    T, inl = cv2.estimateAffinePartial2D(pa, pb, ransacReprojThreshold=3)
                    if T is not None and inl.sum() >= 40 and abs(np.hypot(T[0, 0], T[1, 0]) - 1) < 0.03:
                        same = True
        (dropped if same else k3).append(c)
    return k3, dropped


def shot_motion(cap, a: float, b: float, y0: int, y1: int, orb=None) -> dict:
    orb = orb or cv2.ORB_create(1500)
    A = _gray(cap, a + 0.07, y0, y1)
    B = _gray(cap, max(a + 0.07, b - 0.1), y0, y1)
    if A is None or B is None:
        return {"t0": round(a, 3), "t1": round(b, 3), "motion": "still?"}
    d = float(np.abs(A.astype(int) - B.astype(int)).mean())
    info = {"t0": round(a, 3), "t1": round(b, 3), "diff": round(d, 1)}
    ka, da = orb.detectAndCompute(A, None)
    kb, db = orb.detectAndCompute(B, None)
    mo = "cam"
    if d < 4:
        mo = "still"
    elif da is not None and db is not None and len(ka) > 20 and len(kb) > 20:
        mt = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
        if len(mt) >= 15:
            pa = np.float32([ka[m.queryIdx].pt for m in mt])
            pb = np.float32([kb[m.trainIdx].pt for m in mt])
            T, inl = cv2.estimateAffinePartial2D(pa, pb, ransacReprojThreshold=4)
            if T is not None and inl.sum() >= 12:
                s = float(np.hypot(T[0, 0], T[1, 0]))
                tx, ty = float(T[0, 2]), float(T[1, 2])
                info.update(scale=round(s, 3), tx=round(tx), ty=round(ty), inl=int(inl.sum()))
                if s > 1.025:
                    mo = "zoom_in"
                elif s < 0.975:
                    mo = "zoom_out"
                elif abs(tx) > 25 or abs(ty) > 25:
                    mo = "pan"
                elif d < 10:
                    mo = "still"
    info["motion"] = mo
    return info


def run(mp4: str, C: dict, y0: int, y1: int, sy0: int | None = None, sy1: int | None = None) -> dict:
    cap = cv2.VideoCapture(mp4)
    dur = C["n"] / 30
    k2, dropped = clean_cuts(cap, C["cuts"], sy0 if sy0 is not None else y0, sy1 if sy1 is not None else y1)
    orb = cv2.ORB_create(1500)
    bounds = [0.0] + [c["t"] for c in k2] + [dur]
    shots = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 0.15:
            continue
        shots.append(shot_motion(cap, a, b, y0, y1, orb))
    cap.release()
    return {"dropped_same_picture": dropped, "cuts": k2, "shots": shots}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    sb = None
    if "--same-band" in a:
        i = a.index("--same-band")
        sb = [int(x) for x in a[i + 1].split(",")]
        del a[i:i + 2]
    if len(a) < 5:
        print(__doc__)
        return 2
    mp4, cj, y0, y1, out = a[0], a[1], int(a[2]), int(a[3]), a[4]
    C = json.load(open(cj, encoding="utf-8"))
    r = run(mp4, C, y0, y1, *(sb or (None, None)))
    json.dump(r, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    sh = r["shots"]
    print("dropped", len(r["dropped_same_picture"]), "cuts", len(r["cuts"]), "shots", len(sh), {m: sum(s["motion"] == m for s in sh) for m in set(s["motion"] for s in sh)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
