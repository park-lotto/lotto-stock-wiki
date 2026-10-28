# -*- coding: utf-8 -*-
"""흰 글자 띠 + 장면 움직임 전 프레임 실측(measure) 과 덩어리 요약(seg).

어디서 왔나: 06 홈디자인노트 워커(관제 263, 10-25)의 세션 임시 폴더 도구 measure.py·seg.py 를 한 파일로 옮김(알고리즘 바꾸지 않음).
capseg 와 무엇이 다른가: capseg = '검정 외곽 옆 밝은 채움'(색 글자+검정 외곽) 마스크 IoU. 이 도구 = **흰 저채도 글자**(V>215 & S<60,
            외곽 색 무관) 마스크의 이웃 프레임 변화량 cap_ch · 그리고 cutdet 에 없는 **광류 움직임**(줌 발산 div·이동 tx/ty) ·
            자막 띠를 가린 장면 차이 sd·히스토그램 hd · 평균 밝기 lum(번쩍/검정).
무엇을 재나(measure): 30fps 전 프레임 rows[{i,t,ink,cap_ch,sd,hd,lum,div,tx,ty}]
요약(seg): 컷 = (hd>0.25 & sd>12) 또는 sd>28(3프레임 안은 큰 쪽) · 종류 black(밝기<18)/flash(+45 & >200)/cut ·
           자막 덩어리 = ink>=ink_min 켜짐 + cap_ch>cap_th 면 새 덩어리 · 덩어리별 div·tr·sd 중앙값(컷 ±0.07초 제외)
입력: mp4 · 자막 띠 b0 b1 (예: 홈디자인노트 DCXQjaWcZ-g 570 665)
출력: measure → json {fps, band, rows} · seg → 표준출력(옛 꼴 그대로) + 함수는 {cuts, segs}

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/measure.py <mp4> <out.json> <b0> <b1>
    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/measure.py seg <m.json> [cap_th 0.45] [ink_min 400]
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np


def measure(mp4: str, b0: int, b1: int) -> dict:
    cap = cv2.VideoCapture(mp4)
    fps = cap.get(cv2.CAP_PROP_FPS)
    rows = []
    prev_m = None
    prev_md = None
    prev_g = None
    prev_h = None
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        band = f[b0:b1]
        hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
        m = ((hsv[..., 2] > 215) & (hsv[..., 1] < 60)).astype(np.uint8)
        ink = int(m.sum())
        md = cv2.dilate(m, np.ones((5, 5), np.uint8))
        ch = None
        if prev_m is not None:
            a = (m > 0) & (prev_md == 0)
            b = (prev_m > 0) & (md == 0)
            ch = round(float(a.sum() + b.sum()) / max(1, ink + int(prev_m.sum())), 3)
        prev_m = m
        prev_md = md
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        g2 = g.copy()
        g2[b0:b1] = 0
        s = cv2.resize(g2, (108, 192), interpolation=cv2.INTER_AREA)
        h = cv2.calcHist([s], [0], None, [32], [0, 256])
        cv2.normalize(h, h)
        sd = None
        div = None
        tx = None
        ty = None
        if prev_g is not None:
            sd = round(float(np.abs(s.astype(int) - prev_g.astype(int)).mean()), 2)
            hd = round(float(cv2.compareHist(h, prev_h, cv2.HISTCMP_BHATTACHARYYA)), 3)
            fl = cv2.calcOpticalFlowFarneback(prev_g, s, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            yy, xx = np.mgrid[0:192, 0:108]
            cx, cy = 54, 96
            rx, ry = xx - cx, yy - cy
            r2 = rx * rx + ry * ry + 1e-6
            div = round(float(((fl[..., 0] * rx + fl[..., 1] * ry) / r2).mean()) * 100, 3)
            tx = round(float(fl[..., 0].mean()), 2)
            ty = round(float(fl[..., 1].mean()), 2)
        else:
            hd = None
        rows.append({"i": i, "t": round(i / fps, 3), "ink": ink, "cap_ch": ch, "sd": sd, "hd": hd, "lum": round(float(g.mean()), 1),
                     "div": div, "tx": tx, "ty": ty})
        prev_g = s
        prev_h = h
        i += 1
    cap.release()
    return {"fps": fps, "band": [b0, b1], "rows": rows}


def summarize(M: dict, cth: float = 0.45, imin: int = 400) -> dict:
    R = M["rows"]
    fps = M["fps"]
    cuts = []
    for k, r in enumerate(R):
        if r["hd"] is None:
            continue
        if (r["hd"] > 0.25 and r["sd"] > 12) or r["sd"] > 28:
            if cuts and r["i"] - cuts[-1]["i"] <= 3:
                if r["sd"] > cuts[-1]["sd"]:
                    cuts[-1] = dict(r)
                continue
            cuts.append(dict(r))

    def trans(c):
        k = c["i"]
        w = R[max(0, k - 4):k + 5]
        lums = [x["lum"] for x in w]
        base = np.median([x["lum"] for x in R[max(0, k - 15):k + 15]])
        if min(lums) < 18:
            return "black"
        if max(lums) > base + 45 and max(lums) > 200:
            return "flash"
        return "cut"
    cut_out = [{"t": round(c["t"], 2), "kind": trans(c), "sd": c["sd"], "hd": c["hd"]} for c in cuts]
    segs = []
    cur = None
    for r in R:
        on = r["ink"] >= imin
        if not on:
            if cur:
                cur["t1"] = r["t"]
                segs.append(cur)
                cur = None
            continue
        if cur is None:
            cur = {"t0": r["t"], "i0": r["i"], "ink": []}
        elif r["cap_ch"] is not None and r["cap_ch"] > cth:
            cur["t1"] = r["t"]
            segs.append(cur)
            cur = {"t0": r["t"], "i0": r["i"], "ink": []}
        cur["ink"].append(r["ink"])
    if cur:
        cur["t1"] = round(len(R) / fps, 3)
        segs.append(cur)
    cutt = [c["t"] for c in cuts]
    seg_out = []
    for s in segs:
        a, b = int(round(s["t0"] * fps)), int(round(s["t1"] * fps))
        rr = [x for x in R[a + 1:b] if x["div"] is not None and not any(abs(x["t"] - c) < 0.07 for c in cutt)]
        dv = np.median([x["div"] for x in rr]) if rr else 0
        tr = np.median([abs(x["tx"]) + abs(x["ty"]) for x in rr]) if rr else 0
        sdm = np.median([x["sd"] for x in rr]) if rr else 0
        ink = s["ink"]
        seg_out.append({"t0": s["t0"], "t1": s["t1"], "ink_med": int(np.median(ink)), "first6": ink[:6], "div": float(dv), "tr": float(tr),
                        "sd": float(sdm), "cuts": [round(c, 2) for c in cutt if s["t0"] - 0.05 <= c < s["t1"]]})
    return {"cuts": cut_out, "segs": seg_out}


def print_summary(S: dict) -> None:
    print("CUTS:", [(c["t"], c["kind"], c["sd"], c["hd"]) for c in S["cuts"]])
    for s in S["segs"]:
        print(f'{s["t0"]:6.2f}-{s["t1"]:6.2f} ink_med={s["ink_med"]} first6={s["first6"]} div={s["div"]:.2f} tr={s["tr"]:.2f} sd={s["sd"]:.1f} cuts={s["cuts"]}')


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a and a[0] == "seg":
        if len(a) < 2:
            print(__doc__)
            return 2
        M = json.load(open(a[1]))
        cth = float(a[2]) if len(a) > 2 else 0.45
        imin = int(a[3]) if len(a) > 3 else 400
        print_summary(summarize(M, cth, imin))
        return 0
    if len(a) < 4:
        print(__doc__)
        return 2
    mp4, out, b0, b1 = a[0], a[1], int(a[2]), int(a[3])
    M = measure(mp4, b0, b1)
    json.dump(M, open(out, "w"))
    print(out, len(M["rows"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
