# -*- coding: utf-8 -*-
"""cuts — T.cut_* T.first_cut T.var T.longest_still T.cut_eq_sub T.zoom  장면 컷과 컷 리듬.

컷 = ffmpeg select=gt(scene,SCENE_T) on **영상창 crop**(layout) → 첫 CUT_MIN_T 제외 → CUT_MERGE_S 병합
     → 앞뒤 프레임 상관 < CUT_VERIFY_CORR 인 것만(cut_verify, 창 위쪽 65%) — 설계 §1 "장면 컷".
자막 교체 시각은 captions 결과를 받는다(여기서 다시 재지 않는다).
"""
from __future__ import annotations

import re
import statistics as st

import numpy as np
import cv2

from . import probe
from .constants import (CUT_MERGE_S, CUT_MIN_T, CUT_VERIFY_CORR, CUT_VERIFY_TOP, CUT_SUB_TOL, ZOOM_FPS)
from . import constants as C


def scene_detect(path: str, window: list[int], threshold: float | None = None) -> list[float]:
    """영상창 crop의 scene 점수 > T 시각(첫 CUT_MIN_T 제외). T 기본값 = constants.SCENE_T(호출 때 읽는다)."""
    T = C.SCENE_T if threshold is None else threshold
    x, y, w, h = window
    log = probe.ffmpeg_log(["-i", path, "-an", "-vf", f"crop={w}:{h}:{x}:{y},select='gt(scene,{T})',showinfo",
                            "-f", "null", "-"])
    return [round(float(t), 3) for t in re.findall(r"pts_time:\s*([\d.]+)", log) if float(t) > CUT_MIN_T]


def merge_close(ts: list[float]) -> list[float]:
    """CUT_MERGE_S 안에 붙은 검출은 앞의 것 하나로."""
    out: list[float] = []
    for t in ts:
        if not out or t - out[-1] >= CUT_MERGE_S:
            out.append(t)
    return out


def cut_verify(path: str, window: list[int], cands: list[float], fps: float) -> tuple[list[float], list]:
    """컷 앞(k−1)·뒤(k+1) 프레임의 창 위쪽 65% 64×64 z정규화 상관 < CUT_VERIFY_CORR 이면 진짜 컷."""
    if not cands:
        return [], []
    x, y, w, h = window
    hh = int(h * CUT_VERIFY_TOP)
    sig = []
    for g in probe.frames(path, f"crop={w}:{hh}:{x}:{y},scale=64:64", 64, 64, "gray"):
        a = g.astype(np.float64).ravel()
        sig.append((a - a.mean()) / (a.std() + 1e-6))
    keep, corr = [], []
    for t in cands:
        k = int(round(t * fps))
        if k - 1 < 0 or k + 1 >= len(sig):
            keep.append(t); corr.append(None)
            continue
        c = float((sig[k - 1] * sig[k + 1]).mean())
        corr.append(round(c, 3))
        if c < CUT_VERIFY_CORR:
            keep.append(t)
    return keep, corr


def shot_lengths(cuts: list[float], duration: float) -> list[float]:
    return [b - a for a, b in zip([0.0] + cuts, cuts + [duration])]


def cut_eq_sub(cuts: list[float], sub_changes: list[float]) -> tuple[int, int]:
    """컷 중 자막 교체와 ±CUT_SUB_TOL 안에 겹치는 수 / 컷 수."""
    return sum(1 for t in cuts if any(abs(t - s) <= CUT_SUB_TOL for s in sub_changes)), len(cuts)


def still_gaps(cuts: list[float], sub_changes: list[float], duration: float) -> list[float]:
    """컷·자막 교체를 합친 변화 사건 사이 간격(0.1s 반올림 사건)."""
    ev = sorted(set([round(t, 1) for t in cuts] + [round(t, 1) for t in sub_changes]))
    return [b - a for a, b in zip([0.0] + ev, ev + [duration])]


def zoom_track(path: str, window: list[int], cuts: list[float]) -> list[tuple[float, float]]:
    """영상창 안 이웃 표본 배율(ORB + 부분 아핀, film zoom_track). 컷 경계는 건너뛴다."""
    x, y, w, h = window
    sw = 270
    sh = int(round(sw * h / w / 2) * 2)
    orb = cv2.ORB_create(600)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    cutset = np.array(cuts) if cuts else np.array([1e9])
    prev = None
    out = []
    for i, g in enumerate(probe.frames(path, f"fps={ZOOM_FPS},crop={w}:{h}:{x}:{y},scale={sw}:{sh}", sw, sh, "gray")):
        t = i / ZOOM_FPS
        kp, de = orb.detectAndCompute(g, None)
        if (prev is not None and de is not None and prev[1] is not None
                and np.min(np.abs(cutset - (t - 0.5 / ZOOM_FPS))) > 0.6 / ZOOM_FPS):
            ms = bf.match(prev[1], de)
            if len(ms) >= 25:
                a = np.float32([prev[0][m.queryIdx].pt for m in ms])
                b = np.float32([kp[m.trainIdx].pt for m in ms])
                M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2.0)
                if M is not None and inl.sum() >= 20:
                    out.append((round(t, 2), round(float(np.sqrt(M[0, 0] ** 2 + M[0, 1] ** 2)), 5)))
        prev = (kp, de)
    return out


def zoom_summary(zt: list[tuple[float, float]]) -> dict | None:
    if not zt:
        return None
    rate = np.log(np.array([s for _, s in zt])) * ZOOM_FPS * 100  # %/s
    return {"n": len(zt), "median_rate_pct_s": round(float(np.median(rate)), 2),
            "p90_abs_rate_pct_s": round(float(np.percentile(np.abs(rate), 90)), 2),
            "zoomin_frac": round(float((rate > 1.0).mean()), 3), "zoomout_frac": round(float((rate < -1.0).mean()), 3)}


def measure_video(path: str, vl: dict, meta: dict, sub_changes: list[float], zoom: bool = True) -> dict:
    """편 하나의 컷. 창을 못 찾은 편은 빈 결과."""
    win = vl.get("window")
    if not win:
        return {"cuts": None}
    dur = meta["duration"]
    raw = scene_detect(path, win)
    cands = merge_close(raw)
    cuts, corr = cut_verify(path, win, cands, meta["fps"])
    segs = shot_lengths(cuts, dur)
    eq, n = cut_eq_sub(cuts, sub_changes) if sub_changes else (None, len(cuts))
    gaps = still_gaps(cuts, sub_changes, dur)
    raw_segs = shot_lengths(raw, dur)
    # 병합·검증 전(scene>T 그대로)의 값 — 옛 자(cuts.py·rhythm_stats, 함수 지도 §1-B)와 같은 정의라 기준선 재현 확인용
    raw_stats = {"shots": len(raw) + 1, "first_cut": round(raw_segs[0], 2), "cut_std": round(st.pstdev(raw_segs), 2),
                 "cut_eq_sub": list(cut_eq_sub(raw, sub_changes)) if sub_changes else None}
    res = {"scene_t": C.SCENE_T, "raw": raw, "raw_stats": raw_stats, "candidates": cands, "corr": corr, "cuts": cuts,
           "merged_out": [t for t in raw if t not in cands],
           "rejected": [t for t, c in zip(cands, corr) if c is not None and c >= CUT_VERIFY_CORR],
           "shots": len(cuts) + 1,
           "shot_median": round(st.median(segs), 2), "shot_min": round(min(segs), 2), "shot_max": round(max(segs), 2),
           "first_cut": round(segs[0], 2), "cut_std": round(st.pstdev(segs), 2),
           "cut_per_min": round(len(cuts) / dur * 60, 1),
           "cut_eq_sub": [eq, n] if eq is not None else None,
           "longest_still": round(max(gaps), 2), "event_gap_med": round(st.median(gaps), 2)}
    if zoom:
        res["zoom"] = zoom_summary(zoom_track(path, win, cuts))
    return res


def summarize(per_video: dict[str, dict], vids: list[str]) -> dict:
    got = [(v, per_video[v]["cuts"]) for v in vids if per_video[v].get("cuts", {}).get("cuts") is not None]
    if not got:
        return {}

    def dist(key, k=2, unit="초"):
        a = [c[key] for _, c in got]
        return {"value": round(float(np.median(a)), k), "stat": "median", "range": [round(float(min(a)), k), round(float(max(a)), k)],
                "n": len(a), "unit": unit, "per_video": {v: c[key] for v, c in got}}

    crit = {
        "T.cut_count": {**dist("shots", 0, "샷/편(컷 경계+1)"), "scene_t": C.SCENE_T, "method": "cuts.scene_detect+cuts.merge_close+cuts.cut_verify"},
        "T.cut_sec": {**dist("shot_median"), "method": "cuts.shot_lengths"},
        "T.cut_per_min": {**dist("cut_per_min", 1, "컷/분"), "method": "cuts.shot_lengths"},
        "T.first_cut": {**dist("first_cut"), "method": "cuts.shot_lengths"},
        "T.var": {**dist("cut_std"), "method": "cuts.shot_lengths"},
        "T.longest_still": {**dist("longest_still"), "method": "cuts.still_gaps"},
        "T.event_gap": {**dist("event_gap_med"), "method": "cuts.still_gaps"},
    }
    eq = [(v, c["cut_eq_sub"]) for v, c in got if c.get("cut_eq_sub")]
    if eq:
        pct = [round(100 * a / max(b, 1)) for _, (a, b) in eq]
        crit["T.cut_eq_sub"] = {"value": float(np.median(pct)), "stat": "median", "range": [min(pct), max(pct)], "n": len(pct),
                                "unit": "%", "per_video": {v: f"{a}/{b}" for v, (a, b) in eq}, "method": "cuts.cut_eq_sub"}
    zs = [c["zoom"]["median_rate_pct_s"] for _, c in got if c.get("zoom")]
    if zs:
        crit["T.zoom_rate"] = {"value": round(float(np.median(zs)), 2), "stat": "median of per-video median", "n": len(zs),
                               "unit": "%/s", "method": "cuts.zoom_track"}
    return crit
