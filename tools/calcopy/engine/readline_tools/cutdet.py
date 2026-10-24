# -*- coding: utf-8 -*-
"""컷 검출(cutdet) — 창 안 매 프레임 밝기차·히스토그램차로 컷·전환 종류·샷별 움직임.

어디서 왔나: 06 잇템로그 워커(관제 263, 10-24)의 세션 임시 폴더 도구 cutdet.py 를 그대로 옮김(알고리즘 바꾸지 않음).
무엇을 재나: 창[y0,y1)을 360폭 회색으로 줄여 프레임차 > max(12, 3.5×이웃 중앙값) 또는 히스토그램차 > 0.35 = 컷(2프레임 안 붙은 것 합침).
            컷 앞뒤 ±4프레임 최소 밝기 <10 = black, 앞뒤보다 +50 밝으면 flash, 선명도(라플라시안)가 앞뒤 45% 미만 3프레임↑ = zoomblur, 나머지 cut.
            샷마다 첫·끝 프레임 평균차 chg(움직임 신호 — build_lr 은 6 미만을 still 로 본다).
입력: mp4 · 창 y0 y1 (줄판독 layout.window 의 세로, 예: 잇템로그 486 1920)
출력(json): {n(프레임 수), cuts:[{t, t_end, kind, diff, blurfr}], shots:[{t0, t1, chg}]}

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/cutdet.py <mp4> <y0> <y1> <out.json> [--v2 [--cap-band y0,y1]]
--v2(10-25 추가, 06 키치잇 결손): 자막 띠를 뺀 라플라시안으로 컷 직후 7프레임·직전 6프레임 블러(바탕의 50% 밑 2프레임↑)를 zoomblur 로,
     영상 시작 블러를 t=0 사건으로, 샷마다 shotmotion.shot_motion(ORB 닮음변환 — 배율·이동)으로 motion still/cam/zoom_in/zoom_out/pan.
     옛 분류는 kind_v1 에 남는다. v2 없이 부르면 출력은 옛 도구와 같다.
"""
from __future__ import annotations

import json
import subprocess
import sys

from pathlib import Path

import cv2
import numpy as np

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def cutdet(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080, v2: bool = False, cap_band: tuple | None = None) -> dict:
    """v2=False = 옛 도구 그대로(재현). v2=True = 자막 띠를 뺀 선명도로 전환 종류를 다시 가르고(kind, 옛 값은 kind_v1),
    영상 시작 블러를 사건으로 더하고, 샷마다 shotmotion 움직임(motion: still/cam/zoom_in/zoom_out/pan)을 붙인다(06 키치잇 10-25 결손)."""
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
    if v2:
        _refine_v2(F, mean, res, shots, fps, h, y0, cap_band, mp4, y1)
    return {"n": n, "cuts": res, "shots": shots, **({"v2": True} if v2 else {})}


V2_LOW = 0.5        # 바탕 선명도의 이 비율 밑 = 흐린 프레임
V2_MIN_FR = 3       # 흐린 프레임이 컷 직후 7프레임(또는 직전 6프레임) 안에 이만큼 → zoomblur (키치잇 눈 정답: 2 면 cut 3곳 오탐, 3 이면 0)


def _masked_sharp(F, h, y0, cap_band):
    keep = np.ones(h, bool)
    if cap_band:
        r0 = max(0, int((cap_band[0] - y0) / 3) - 3)
        r1 = min(h, int((cap_band[1] - y0) / 3) + 3)
        keep[r0:r1] = False
    return np.array([cv2.Laplacian(f[keep], cv2.CV_32F).var() for f in F])


def _refine_v2(F, mean, res, shots, fps, h, y0, cap_band, mp4, y1):
    n = len(F)
    sh = _masked_sharp(F, h, y0, cap_band)
    for r in res:
        r["kind_v1"] = r["kind"]
        if r["kind"] in ("black", "flash"):
            continue
        a = int(round(r["t"] * fps))
        b = int(round(r["t_end"] * fps))
        post_base = np.median(sh[min(n - 1, b + 8):min(n, b + 18)]) if b + 9 < n else np.nan
        pre_base = np.median(sh[max(0, a - 18):max(1, a - 8)]) if a - 9 > 0 else np.nan
        post_low = int((sh[b:min(n, b + 7)] < V2_LOW * post_base).sum()) if post_base == post_base else 0
        pre_low = int((sh[max(0, a - 6):a] < V2_LOW * pre_base).sum()) if pre_base == pre_base else 0
        r["blur_post"] = post_low
        r["blur_pre"] = pre_low
        if r["kind"] == "zoomblur" or post_low >= V2_MIN_FR or pre_low >= V2_MIN_FR:
            r["kind"] = "zoomblur"
    if n > 20:                                   # 영상 시작 블러(컷이 없다): 첫 6프레임이 8~20프레임 바탕보다 흐림
        base = np.median(sh[8:20])
        low = int((sh[:6] < V2_LOW * base).sum())
        recovered = float(sh[5:8].mean()) >= 0.85 * base   # 블러는 몇 프레임 안에 선명해진다(키치잇 Cs-Ka: 0.47→0.51 평평 = 블러 아님)
        if low >= 2 and recovered:
            res.insert(0, {"t": 0.0, "t_end": 0.0, "kind": "zoomblur", "diff": 0.0, "blurfr": low, "start": True, "kind_v1": None})
    from tools.calcopy.engine.readline_tools.shotmotion import shot_motion   # 움직임 주인 = shotmotion(ORB 닮음변환, 유머쇼쇼 워커 motion.py)
    cap = cv2.VideoCapture(mp4)
    orb = cv2.ORB_create(1500)
    for s in shots:
        if s["t1"] - s["t0"] < 0.15:
            s["motion"] = "still?"
            continue
        cut = next((c for c in res if abs(c["t"] - s["t0"]) < 0.5 / fps), None)
        skip = (cut.get("blur_post") or cut.get("blurfr") or 0) / fps if cut and cut["kind"] == "zoomblur" else 0.0
        a = min(s["t0"] + skip, max(s["t0"], s["t1"] - 0.3))     # 블러 프레임은 ORB 가 못 잡는다 → 블러가 풀린 뒤부터
        m = shot_motion(cap, a, s["t1"], y0, y1, orb)
        s["motion"] = m["motion"]
        s.update({k: m[k] for k in ("scale", "tx", "ty") if k in m})
    cap.release()


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 4:
        print(__doc__)
        return 2
    v2 = "--v2" in a
    cb = None
    if "--cap-band" in a:
        i = a.index("--cap-band")
        cb = tuple(int(x) for x in a[i + 1].split(","))
        del a[i:i + 2]
    a = [x for x in a if x != "--v2"]
    mp4, y0, y1, out = a[0], int(a[1]), int(a[2]), a[3]
    d = cutdet(mp4, y0, y1, v2=v2, cap_band=cb)
    json.dump(d, open(out, "w"), indent=0)
    for r in d["cuts"]:
        print(r)
    print("shots", len(d["shots"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
