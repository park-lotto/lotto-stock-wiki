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


V2 = dict(WIN=8, DIP=0.60, REC=0.80, LONG=12, FLASH=40.0, FILL_STD=6.0, BLACK=20.0, TINT=45.0)
# ↑ 전환 4종 측정 규칙 — 표준 §11-8 ㊴(페이블 8차 결정, 10-25). 렌더에 닿는 종류만: cut · flash · zoomblur · black.
#   zoomblur = 경계 ±WIN 프레임 안 선명도(라플라시안 분산, 창·자막 마스크)가 경계 직전 수준의 ≤DIP 로 떨어지고
#              양쪽 모두 WIN 프레임 안에 ≥REC 로 회복(직전 쪽 = 직전 수준, 뒤쪽 = 같은 샷 뒤 수준)
#   cut + blur_tail = 흐림이 LONG 프레임 넘게 이어지거나 한쪽만 회복(소스 자체의 모션 블러·초점 흐림 = 전환 아님)
#   flash = 경계 1~4프레임 밝기(Y 평균) 피크 ≥ 직전 +FLASH, 또는 단색 채움 프레임(표준편차 ≤FILL_STD, 검정 아님)
#   black = 경계 1~4프레임 Y 평균 ≤BLACK
#   (조정 1회, 13 표) 색 채움 = 화면 전체 색편차(G−(R+B)/2·R−(G+B)/2)가 +TINT 뛰고 14프레임 안에 절반 넘게 빠짐 → flash 의 '단색 채움'으로 셈
#   그 밖(장면이 바뀌며 생긴 색 점프·샷 바뀜만) = cut


def _med(x, lo, hi):
    lo, hi = max(0, lo), min(len(x), hi)
    return float(np.median(x[lo:hi])) if hi - lo >= 1 else float("nan")


def decide(f: dict, P: dict | None = None) -> str:
    """특징 → 종류(4종). classify_arrays 가 부르고, 점검 도구가 같은 함수를 부른다. blur_tail 은 classify_arrays 가 따로 붙인다."""
    P = dict(V2, **(P or {}))
    if f["y_min"] <= P["BLACK"]:
        return "black"
    if f["y_peak_jump"] >= P["FLASH"] or f["fill"] or f.get("tint", 0.0) >= P["TINT"]:
        return "flash"
    if f["dip_ratio"] <= P["DIP"] and f["rec_left"] and f["rec_right"] and f["blur_len"] <= P["LONG"]:
        return "zoomblur"
    return "cut"


BORDER = dict(DIP=(0.50, 0.60), FLASH=(40.0, 55.0))   # 경계 띠 — 이 안이면 초안에 border:true(06 시트에서 눈 확정, 자동 단독 금지 ㊵)


def _border(f: dict, P: dict) -> bool:
    """경계 띠(움푹 0.5~0.6 · Y 피크 40~55) 또는 종류 조건이 둘 이상 겹침(검정·번쩍·블러)."""
    hits = [f["y_min"] <= P["BLACK"], f["y_peak_jump"] >= P["FLASH"] or f["fill"] or f.get("tint", 0.0) >= P["TINT"],
            f["dip_ratio"] <= P["DIP"] and f["rec_left"] and f["rec_right"] and f["blur_len"] <= P["LONG"]]
    return bool(BORDER["DIP"][0] < f["dip_ratio"] <= BORDER["DIP"][1] or BORDER["FLASH"][0] <= f["y_peak_jump"] < BORDER["FLASH"][1] or sum(hits) >= 2)


def classify_arrays(A: dict, groups: list[tuple[int, int]], fps: float = 30.0, P: dict | None = None) -> list[dict]:
    """전환 종류의 주인 함수 — 프레임 배열(A: mean(Y)·sh(자막 띠 뺀 선명도)·std)과 컷 묶음(시작,끝 프레임)으로
    경계마다 {t, te, kind(4종), blur_tail, 특징…}. cutdet --v2·확인 시트(transsheet)·LOCO 점검이 같은 함수를 부른다."""
    P = dict(V2, **(P or {}))
    W = int(P["WIN"])
    mean, sh = A["mean"], A["sh"]
    std = A.get("std")
    n = len(mean)
    Sg = Sr = None
    if A.get("r") is not None:
        Sg, Sr = A["g"] - (A["r"] + A["b"]) / 2, A["r"] - (A["g"] + A["b"]) / 2
    cutf = [g[0] for g in groups]
    out = []
    for (s, e) in groups:
        nxt = min([c for c in cutf if c > e + 1] + [n])
        prv = max([c for c in cutf if c < s] + [0])
        pre = _med(sh, max(prv, s - 12), s - 1) if s - 1 > max(prv, s - 12) else float(sh[max(0, s - 1)])
        post = _med(sh, e + W + 1, min(nxt, e + W + 13)) if nxt - (e + W + 1) >= 3 else _med(sh, e + W + 1, e + W + 13)
        lo, hi = max(0, s - W), min(n, e + W + 1)
        seg = sh[lo:hi]
        k = int(np.argmin(seg)) + lo if len(seg) else s
        ref_r = post if post == post and post > 0 else (pre if pre == pre and pre > 0 else 1.0)
        at_start = s <= W and prv == 0                          # 영상 첫머리 경계: 앞 샷이 없다(첫 프레임부터 흐린 시작 블러 — 키치잇 Ks5k·cNo)
        ref_l = ref_r if at_start else (pre if pre == pre and pre > 0 else 1.0)
        dip_ratio = float(sh[k] / min(ref_l, ref_r)) if len(seg) else 1.0    # 양쪽 샷 평소 수준 모두보다 낮아야 '움푹' — 선명→흐린 샷으로의 그냥 컷을 빼는 조정(1회)
        rec_left = True if at_start else (bool(np.any(sh[max(0, k - W):k] >= P["REC"] * ref_l)) if k > 0 else False)
        rec_right = bool(np.any(sh[k + 1:min(n, k + W + 1)] >= P["REC"] * ref_r))
        low = sh < P["DIP"] * min(ref_l, ref_r)
        a = b = k
        while a > 0 and low[a - 1]:
            a -= 1
        while b + 1 < n and low[b + 1]:
            b += 1
        blur_len = int(b - a + 1) if low[k] else 0
        b0, b1 = s, min(n, s + 4)
        pre_y = _med(mean, max(prv, s - 8), s - 1) if s - 1 > max(prv, s - 8) else float(mean[max(0, s - 1)])
        y_peak = float(mean[b0:b1].max()) if b1 > b0 else float(mean[min(n - 1, s)])
        post_y = _med(mean, e + W + 1, min(nxt, e + W + 13)) if nxt - (e + W + 1) >= 3 else _med(mean, e + W + 1, e + W + 13)
        post_y = post_y if post_y == post_y else pre_y
        y_min = float(mean[b0:b1].min()) if b1 > b0 else float(mean[min(n - 1, s)])
        fill = bool(std is not None and b1 > b0 and np.any((std[b0:b1] <= P["FILL_STD"]) & (mean[b0:b1] > P["BLACK"])))
        tint = 0.0
        for S in ((Sg, Sr) if Sg is not None else ()):
            for i in range(max(1, s - 2), min(len(S) - 15, s + 3)):
                j = float(S[i] - S[i - 1])
                if j > tint and S[i] - S[i + 14] > 0.5 * j and S[i] >= S[i + 1] - 2:
                    tint = j
        f = {"t": round(s / fps, 3), "te": round(e / fps, 3), "dip_ratio": round(dip_ratio, 2), "dip_at": round(k / fps, 3),
             "rec_left": rec_left, "rec_right": rec_right, "blur_len": blur_len, "y_peak_jump": round(y_peak - max(pre_y, post_y), 1),   # 피크 = 앞·뒤 샷 모두보다 밝음(조정 1회)
             "y_min": round(y_min, 1), "fill": fill, "tint": round(tint, 1)}
        f["kind"] = decide(f, P)
        f["blur_tail"] = bool(f["kind"] == "cut" and dip_ratio <= P["DIP"])     # 흐려지긴 했지만 효과 지문(대칭·짧음)이 아님
        f["border"] = _border(f, P)
        out.append(f)
    if n > 2 * W + 13 and not (groups and groups[0][0] <= W):   # 영상 시작도 경계(앞이 없다 → 왼쪽은 회복된 것으로 보고 뒤 수준과 견줌)
        post = _med(sh, W + 1, W + 13)
        seg = sh[0:W + 1]
        k = int(np.argmin(seg))
        dr = float(sh[k] / post) if post > 0 else 1.0
        rr = bool(np.any(sh[k + 1:k + W + 1] >= P["REC"] * post))
        low = sh < P["DIP"] * post
        b = k
        while b + 1 < n and low[b + 1]:
            b += 1
        f = {"t": 0.0, "te": 0.0, "start": True, "dip_ratio": round(dr, 2), "dip_at": round(k / fps, 3), "rec_left": True, "rec_right": rr,
             "blur_len": int(b + 1) if low[k] else 0, "y_peak_jump": 0.0, "y_min": round(float(mean[0:4].min()), 1),
             "fill": bool(std is not None and np.any((std[0:4] <= P["FILL_STD"]) & (mean[0:4] > P["BLACK"]))), "tint": 0.0}
        f["kind"] = decide(f, P)
        f["blur_tail"] = False
        f["border"] = _border(f, P)
        if f["kind"] != "cut":
            out.insert(0, f)
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
    """v2: classify_arrays(주인, 표준 §11-8 4종 규칙)로 종류를 다시 매긴다. use_color_flash 는 옛 인자(색 점프만 = cut, 무시)."""
    n = len(F)
    r_, g_, b_ = rgb_means(mp4, y0, y1, fps)
    m = min(n, len(r_))
    A = {"mean": mean, "sh": _masked_sharp(F, h, y0, cap_band), "std": F.std((1, 2)), "dark": (F < 20).mean((1, 2)), "white": (F > 235).mean((1, 2)),
         "r": np.r_[r_[:m], np.full(n - m, r_[m - 1] if m else 0)], "g": np.r_[g_[:m], np.full(n - m, g_[m - 1] if m else 0)],
         "b": np.r_[b_[:m], np.full(n - m, b_[m - 1] if m else 0)]}
    groups = [(int(round(r["t"] * fps)), int(round(r["t_end"] * fps))) for r in res]
    cls = classify_arrays(A, groups, fps)
    by_t = {c["t"]: c for c in cls}
    for r in res:
        r["kind_v1"] = r["kind"]
        c = by_t.get(round(int(round(r["t"] * fps)) / fps, 3))
        if c:
            r.update({k: v for k, v in c.items() if k not in ("t", "te")})
    if cls and cls[0].get("start"):
        res.insert(0, {"t": 0.0, "t_end": 0.0, "diff": 0.0, "kind_v1": None, **{k: v for k, v in cls[0].items() if k not in ("t", "te")}})
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
