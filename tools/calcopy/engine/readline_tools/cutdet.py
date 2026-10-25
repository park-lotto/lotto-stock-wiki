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


def cut_groups(diff, hd) -> list[tuple[int, int]]:
    """컷 찾기의 주인: 프레임차 > max(12, 3.5×이웃 30프레임 중앙값) 또는 히스토그램차 > 0.35, 2프레임 안은 한 묶음 → (시작, 끝)."""
    n = len(diff)
    med = np.array([np.median(diff[max(0, i - 15):i + 15]) for i in range(n)])
    cuts = [i for i in range(1, n) if (diff[i] > max(12, 3.5 * med[i]) or hd[i] > 0.35)]
    cm = []
    for c in cuts:
        if cm and c - cm[-1][-1] <= 2:
            cm[-1].append(c)
        else:
            cm.append([c])
    return [(g[0], g[-1]) for g in cm]


def cutdet(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080, v2: bool = False, cap_band: tuple | None = None,
           use_color_flash: bool = False, motion: bool = True) -> dict:
    """v2=False = 옛 도구 그대로(재현). v2=True = 자막 띠를 뺀 선명도로 전환 종류를 다시 가르고(kind, 옛 값은 kind_v1),
    영상 시작 블러를 사건으로 더하고, 샷마다 shotmotion 움직임(motion: still/cam/zoom_in/zoom_out/pan)을 붙인다(06 키치잇 10-25 결손)."""
    H = y1 - y0
    w, h = 360, int(H / 3)
    from tools.calcopy.engine.readline_tools.capseg import fps_filter      # 60fps 원본 → 30 (주인 = capseg.fps_filter)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", fps_filter(mp4, fps) + f"crop={width}:{H}:0:{y0}:exact=1,scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = len(raw) // (w * h)
    F = np.frombuffer(raw, np.uint8)[:n * w * h].reshape(n, h, w).astype(np.float32)
    mean = F.mean((1, 2))
    sharp = np.array([cv2.Laplacian(f[:int(h * 0.55)], cv2.CV_32F).var() for f in F])
    diff = np.r_[0, [np.abs(F[i] - F[i - 1]).mean((0, 1)) for i in range(1, n)]] if n > 1 else np.zeros(n)   # 프레임마다(긴 영상 통째 빼기는 메모리 2배 — 56초 편에서 MemoryError)
    hist = [cv2.calcHist([f.astype(np.uint8)], [0], None, [32], [0, 256]).ravel() for f in F]
    hist = [x / x.sum() for x in hist]
    hd = np.r_[0, [0.5 * np.abs(hist[i] - hist[i - 1]).sum() for i in range(1, n)]]
    res = []
    for a, b in cut_groups(diff, hd):
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
        _refine_v2(F, mean, res, shots, fps, h, y0, cap_band, mp4, y1, use_color_flash, motion)
    return {"n": n, "cuts": res, "shots": shots, **({"v2": True} if v2 else {})}


def color_flash(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080) -> list[dict]:
    """색 번쩍(06 샤크탱크 워커 fsseg.py 그대로): 창 1/4 크기 평균 색편차 G-(R+B)/2(초록)·R-(G+B)/2(빨강)가 한 프레임에 +12↑ 뛰고
    14프레임 뒤 뛴 양의 절반 넘게 줄면 번쩍. 같은 색 0.2초 안은 하나. 밝기 번쩍(흰)은 cutdet 의 flash(평균 +50)가 잡는다."""
    from tools.calcopy.engine.readline_tools.capseg import fps_filter
    w, h = width // 4, (y1 - y0) // 4
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", fps_filter(mp4, fps) + f"crop={width}:{y1 - y0}:0:{y0}:exact=1,scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = len(raw) // (w * h * 3)
    A = np.frombuffer(raw, np.uint8)[:n * w * h * 3].reshape(n, h, w, 3).astype(float)
    r, g, b = A[..., 0].mean((1, 2)), A[..., 1].mean((1, 2)), A[..., 2].mean((1, 2))
    fl = []
    for name, S in (("초록", g - (r + b) / 2), ("빨강", r - (g + b) / 2)):
        for i in range(1, len(S) - 14):
            j = S[i] - S[i - 1]
            if j > 12 and S[i] - S[min(len(S) - 1, i + 14)] > 0.5 * j and S[i] >= S[i + 1] - 2:
                if not fl or abs(fl[-1]["t"] - i / fps) > 0.2 or fl[-1]["color"] != name:
                    fl.append({"t": round(i / fps, 3), "color": name, "jump": round(float(j), 1)})
    fl.sort(key=lambda e: e["t"])
    return fl


V2_LOW = 0.5        # 바탕 선명도의 이 비율 밑 = 흐린 프레임


def _masked_sharp(F, h, y0, cap_band):
    keep = np.ones(h, bool)
    if cap_band:
        r0 = max(0, int((cap_band[0] - y0) / 3) - 3)
        r1 = min(h, int((cap_band[1] - y0) / 3) + 3)
        keep[r0:r1] = False
    return np.array([cv2.Laplacian(f[keep], cv2.CV_32F).var() for f in F])


V2 = dict(R=0.30, RI=1.5, R2=0.45, RI2=1.75, DK=0.6, DDK=0.3, DM=30.0, FADE=10.0, DEC=25.0, CF=45.0)
# ↑ 전환 분류 문턱 — 14채널 98편 눈 정답(특수 79곳·cut 1287줄)으로 '채널 하나 빼고 맞추기'(LOCO)를 돌려 고른 값(10-25, 표는 README).
#   블러: (같은 샷 바탕 대비 최저 비율 ≤R 이고 다시 선명해짐 ≥RI) 또는 (≤R2 이고 ≥RI2 — 약한 블러는 더 확실히 풀려야)
#   검정: 창 검정 비율 최고 ≥DK 이고 그 샷의 평소 검정 비율(앞·뒤)보다 DDK 이상 높음 — 원래 어두운 장면(이븐쇼핑) 오탐 막음
#   밝기 번쩍: 컷에서 +DM 뛰고 서서히 어두워지며(6프레임 단조) 12프레임 뒤 DEC 이상 내려감 — 밝은 장면으로의 그냥 컷과 가른다
#   색 번쩍: 색편차(G−(R+B)/2·R−(G+B)/2)가 +CF 뛰고 14프레임 안에 절반 넘게 줄어듦(샤크탱크 fsseg 꼴, 문턱만 12→45)


def _med(x, lo, hi):
    lo, hi = max(0, lo), min(len(x), hi)
    return float(np.median(x[lo:hi])) if hi - lo >= 1 else float("nan")


def decide(f: dict, P: dict | None = None) -> str:
    """특징 → 종류(문턱만). classify_arrays 가 부르고, LOCO 점검이 문턱을 바꿔 가며 부른다."""
    P = dict(V2, **(P or {}))
    if f["dark_peak"] >= P["DK"] and f["dark_peak"] - f["dark_around"] >= P["DDK"]:
        return "black"
    if (f["bright_jump"] >= P["DM"] and f["fading"] and f["bright_decay"] >= P["DEC"]) or f["color_jump"] >= P["CF"]:
        return "flash"
    if (f["blur_rise"] >= P["RI"] and f["blur_ratio"] <= P["R"]) or (f["blur_rise"] >= P["RI2"] and f["blur_ratio"] <= P["R2"]):
        return "zoomblur"
    return "cut"


def classify_arrays(A: dict, groups: list[tuple[int, int]], fps: float = 30.0, P: dict | None = None) -> list[dict]:
    """전환 종류의 주인 함수 — 프레임 배열(A: mean·sh(자막 띠 뺀 선명도)·dark·white·r·g·b)과 컷 묶음(시작,끝 프레임)으로
    사건마다 {t, te, kind, 특징…}. cutdet --v2 와 점검 도구(LOCO)가 같은 함수를 부른다."""
    P = dict(V2, **(P or {}))
    mean, sh, dark = A["mean"], A["sh"], A["dark"]
    n = len(mean)
    cutf = [g[0] for g in groups]
    Sg = Sr = None
    if A.get("r") is not None:
        Sg, Sr = A["g"] - (A["r"] + A["b"]) / 2, A["r"] - (A["g"] + A["b"]) / 2
    out = []
    for (s, e) in groups:
        nxt = min([c for c in cutf if c > e + 1] + [n])
        prv = max([c for c in cutf if c < s] + [0])
        base_in = _med(sh, e + 8, min(nxt, e + 18)) if nxt - (e + 8) >= 3 else _med(sh, e + 8, e + 18)
        win = sh[s:min(n, e + 7)]
        ratio = float(win.min() / base_in) if len(win) and base_in == base_in and base_in > 0 else 1.0
        rise = float(sh[min(n - 1, e + 6)] / (win[:3].mean() + 1e-6)) if len(win) else 1.0
        pre_mean = _med(mean, max(prv, s - 8), s - 1) if s - 1 > max(prv, s - 8) else float(mean[max(0, s - 3)])
        pre_dk = _med(dark, max(prv, s - 10), s - 1) if s - 1 > max(prv, s - 10) else float(dark[max(0, s - 3)])
        post_dk = _med(dark, e + 8, min(nxt, e + 20)) if nxt - (e + 8) >= 3 else float(dark[min(n - 1, e + 8)])
        w0, w1 = max(1, s - 1), min(n, e + 6)
        dk_peak = float(dark[w0:w1].max()) if w1 > w0 else 0.0
        jumps = [float(mean[i] - mean[i - 1]) for i in range(max(1, s - 1), min(n, s + 2))]
        big = max(jumps, key=abs) if jumps else 0.0
        pk = int(np.argmax(mean[s:min(n, s + 4)])) + s if s < n else s
        tail = mean[pk:min(n, pk + 6)]
        fading = len(tail) >= 6 and bool(np.all(np.diff(tail) < 0.5)) and float(tail[0] - tail[-1]) >= P["FADE"]
        decay = float(mean[pk] - mean[min(n - 1, pk + 12)])
        cfl = 0.0
        for S in ((Sg, Sr) if Sg is not None else ()):
            for i in range(max(1, s - 2), min(len(S) - 15, s + 3)):
                j = float(S[i] - S[i - 1])
                if j > cfl and S[i] - S[i + 14] > 0.5 * j and S[i] >= S[i + 1] - 2:
                    cfl = j
        f = {"t": round(s / fps, 3), "te": round(e / fps, 3), "blur_ratio": round(ratio, 2), "blur_rise": round(rise, 2),
             "dark_peak": round(dk_peak, 2), "dark_around": round(max(pre_dk, post_dk), 2), "bright_jump": round(big, 1),
             "bright_decay": round(decay, 1), "fading": fading, "color_jump": round(cfl, 1)}
        f["kind"] = decide(f, P)
        out.append(f)
    if n > 20:                                   # 영상 시작 블러(컷이 없다): 첫 6프레임이 8~20프레임 바탕보다 흐리고 몇 프레임 안에 선명해짐
        base = float(np.median(sh[8:20]))
        low = int((sh[:6] < V2_LOW * base).sum())
        if low >= 2 and float(sh[5:8].mean()) >= 0.85 * base:
            out.insert(0, {"t": 0.0, "te": 0.0, "kind": "zoomblur", "start": True, "blurfr": low})
    return out


def rgb_means(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080):
    from tools.calcopy.engine.readline_tools.capseg import fps_filter
    w, h = width // 4, (y1 - y0) // 4
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", fps_filter(mp4, fps) + f"crop={width}:{y1 - y0}:0:{y0}:exact=1,scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = len(raw) // (w * h * 3)
    X = np.frombuffer(raw, np.uint8)[:n * w * h * 3].reshape(n, h, w, 3).astype(np.float32)
    return X[..., 0].mean((1, 2)), X[..., 1].mean((1, 2)), X[..., 2].mean((1, 2))


def _refine_v2(F, mean, res, shots, fps, h, y0, cap_band, mp4, y1, use_color_flash=False, motion=True):
    """v2: classify_arrays(주인)로 종류를 다시 매긴다. use_color_flash 는 옛 인자(10-25 LOCO 뒤 색 번쩍은 늘 켬, 문턱 V2['CF'])."""
    n = len(F)
    r_, g_, b_ = rgb_means(mp4, y0, y1, fps)
    m = min(n, len(r_))
    A = {"mean": mean, "sh": _masked_sharp(F, h, y0, cap_band), "dark": (F < 20).mean((1, 2)), "white": (F > 235).mean((1, 2)),
         "r": np.r_[r_[:m], np.full(n - m, r_[m - 1] if m else 0)], "g": np.r_[g_[:m], np.full(n - m, g_[m - 1] if m else 0)],
         "b": np.r_[b_[:m], np.full(n - m, b_[m - 1] if m else 0)]}
    groups = [(int(round(r["t"] * fps)), int(round(r["t_end"] * fps))) for r in res]
    cls = classify_arrays(A, groups, fps)
    by_t = {c["t"]: c for c in cls if not c.get("start")}
    for r in res:
        r["kind_v1"] = r["kind"]
        c = by_t.get(round(int(round(r["t"] * fps)) / fps, 3))
        if c:
            r.update({k: v for k, v in c.items() if k not in ("t", "te")})
    if cls and cls[0].get("start"):
        res.insert(0, {"t": 0.0, "t_end": 0.0, "kind": "zoomblur", "diff": 0.0, "blurfr": cls[0]["blurfr"], "start": True, "kind_v1": None})
    if not motion:                               # 전환만 볼 때(점검 도구) — 샷마다 ORB 는 느리다
        return
    from tools.calcopy.engine.readline_tools.shotmotion import shot_motion   # 움직임 주인 = shotmotion(ORB 닮음변환, 유머쇼쇼 워커 motion.py)
    cap = cv2.VideoCapture(mp4)
    orb = cv2.ORB_create(1500)
    for s in shots:
        if s["t1"] - s["t0"] < 0.15:
            s["motion"] = "still?"
            continue
        cut = next((c for c in res if abs(c["t"] - s["t0"]) < 0.5 / fps), None)
        skip = (cut.get("blurfr") or 7) / fps if cut and cut["kind"] == "zoomblur" else 0.0   # 블러 창(컷 뒤 7프레임) 뒤부터
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
