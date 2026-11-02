# -*- coding: utf-8 -*-
"""cuts — T.cut_* T.first_cut T.var T.longest_still T.cut_eq_sub T.zoom  장면 컷과 컷 리듬.

컷 = ffmpeg select=gt(scene,SCENE_T) on **영상창 crop**(layout) → 첫 CUT_MIN_T 제외 → CUT_MERGE_S 병합
     → 앞뒤 프레임 상관 < CUT_VERIFY_CORR 인 것만(cut_verify, 창 위쪽 65%) — 설계 §1 "장면 컷".
배경 밝기(layout bg_rgb)를 받으면 창 안 '바탕' 화소(앞뒤 프레임 다 배경색)를 빼고 잰다 — 가변 그림 칸(게시글형)은
칸 밖 흰 바탕이 창의 20~40%라 점수를 희석·상관을 부풀려 소스가 다른 경계를 놓쳤다(2026-10-16 리센느 빵 4개).
raw(scene>T 그대로)는 옛 자 그대로 둔다(기준선 재현용).
자막 교체 시각은 captions 결과를 받는다(여기서 다시 재지 않는다).
"""
from __future__ import annotations

import re
import statistics as st

import numpy as np
import cv2

from . import probe
from .constants import (CUT_MERGE_S, CUT_MIN_T, CUT_VERIFY_CORR, CUT_VERIFY_TOP, CUT_SUB_TOL, ZOOM_FPS,
                        CUT_BG_TOL, CUT_ACTIVE_MIN, CUT_VERIFY_ACTIVE_MIN, CUT_MOVE_INLIERS, CUT_MOVE_SCALE,
                        CUT_MOVE_W, CUT_BG_FPS, CUT_BG_EDGE_FRAC)
from . import constants as C


def bg_gray(vl: dict) -> float | None:
    """layout 결과의 배경 RGB → 회색 밝기(BT.601). 없으면 None(바탕 빼기 안 함)."""
    b = vl.get("bg_rgb") if vl else None
    return None if not b else float(0.299 * b[0] + 0.587 * b[1] + 0.114 * b[2])


def window_bg(path: str, window: list[int]) -> float | None:
    """창 안 바탕 밝기 — 창 네 변 화소(CUT_BG_FPS 표본, 64×64 회색)의 최빈값 v, 그 ±CUT_BG_TOL 안 비율 ≥ CUT_BG_EDGE_FRAC 일 때만 v.
    layout 의 bg_rgb 는 창 '밖' 배경이라 창 안 그림 칸 바탕과 다를 수 있다(방구석 창 밖 240·창 안 흰 칸 255 → 바탕을 못 봄).
    창을 영상이 꽉 채우면 네 변이 제각각이라 None(바탕 빼기 안 함 = 옛 방식)."""
    x, y, w, h = window
    edge = []
    for g in probe.frames(path, f"fps={CUT_BG_FPS},crop={w}:{h}:{x}:{y},scale=64:64", 64, 64, "gray"):
        edge.append(np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]]))
    if not edge:
        return None
    e = np.concatenate(edge).astype(np.int32)
    v = int(np.bincount(e, minlength=256).argmax())
    return float(v) if float((np.abs(e - v) <= CUT_BG_TOL).mean()) >= CUT_BG_EDGE_FRAC else None


def scene_scores(path: str, window: list[int]) -> list[tuple[float, float]]:
    """영상창 crop의 프레임별 ffmpeg scene 점수 [(pts_time, score)] — select=gt(scene,T)가 보는 값 그대로."""
    x, y, w, h = window
    log = probe.ffmpeg_log(["-i", path, "-an", "-vf", f"crop={w}:{h}:{x}:{y},select='gte(scene,0)',metadata=print",
                            "-f", "null", "-"])
    out, t = [], None
    for line in log.splitlines():
        m = re.search(r"pts_time:\s*([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([\d.]+)", line)
        if m and t is not None:
            out.append((t, float(m.group(1))))
            t = None
    return out


def inset(mask: np.ndarray) -> bool:
    """바탕 아닌 화소(mask)가 창 네 변 중 하나라도 닿지 않으면 True — 그림 칸이 창 안에 떠 있다(게시글형 가변 칸).
    네 변 다 닿으면(창을 꽉 채운 영상) 바탕 빼기를 하지 않는다 = 옛 방식 그대로(흰 물건 장면에서 결과가 흔들리지 않게)."""
    return not (mask[0].any() and mask[-1].any() and mask[:, 0].any() and mask[:, -1].any())


def active_fracs(path: str, window: list[int], bg: float) -> np.ndarray:
    """프레임 k마다 'k 또는 k−1 에서 배경색이 아닌' 창 화소 비율(64×64 회색). [0] = 프레임 0 자체.
    그 화소가 창 네 변에 다 닿으면(inset 아님) 1.0 — 보정 없음."""
    x, y, w, h = window
    nb = np.array([np.abs(g.astype(np.float32) - bg) > CUT_BG_TOL
                   for g in probe.frames(path, f"crop={w}:{h}:{x}:{y},scale=64:64", 64, 64, "gray")])
    if not len(nb):
        return np.zeros(0)
    un = nb.copy()
    un[1:] |= nb[:-1]
    return np.array([float(u.mean()) if inset(u) else 1.0 for u in un])


def scene_detect(path: str, window: list[int], threshold: float | None = None,
                 bg: float | None = None, fps: float | None = None) -> list[float]:
    """영상창 crop의 scene 점수 > T 시각(첫 CUT_MIN_T 제외). T 기본값 = constants.SCENE_T(호출 때 읽는다).
    bg(배경 회색)·fps 를 주면 점수를 '바탕 아닌 화소 비율'로 나눠 본 보정 점수로 '보정으로만 넘은' 프레임을 더한다
    (희석 보정, 상한 1/CUT_ACTIVE_MIN 배). 원래 점수로 넘은 프레임(옛 자)은 그대로 두고, 보정으로만 넘은 프레임은
    옛 프레임과 CUT_MERGE_S 안이면 버리고 나머지는 CUT_MERGE_S 묶음마다 보정 점수 최대 하나만 — 약한 앞 프레임이
    진짜 컷을 밀어내지 않게(2026-10-16 방구석 ILIi 원본 5.933(0.19)이 6.0(0.40)을 밀어냄 · 기준선 표본 한 편의
    0.2초 간격 연속 컷 3개를 묶음 최대로 바꾸자 컷 2개를 잃음 → 옛 프레임은 손대지 않는다)."""
    T = C.SCENE_T if threshold is None else threshold
    if bg is not None and fps:
        fr = active_fracs(path, window, bg)
        raw, boost = [], []
        for t, s in scene_scores(path, window):
            if t <= CUT_MIN_T:
                continue
            k = int(round(t * fps))
            a = float(fr[k]) if 0 <= k < len(fr) else 1.0
            e = s / max(a, CUT_ACTIVE_MIN)
            if s > T:
                raw.append(round(t, 3))
            elif e > T:
                boost.append((round(t, 3), e))
        boost = [(t, e) for t, e in boost if not any(abs(t - r) < CUT_MERGE_S - 1e-6 for r in raw)]
        out, grp = [], []
        for t, e in boost:
            if grp and t - grp[0][0] >= CUT_MERGE_S - 1e-6:
                out.append(max(grp, key=lambda x: x[1])[0]); grp = []
            grp.append((t, e))
        if grp:
            out.append(max(grp, key=lambda x: x[1])[0])
        return sorted(raw + out)
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


def _zcorr(a: np.ndarray, b: np.ndarray) -> float:
    a = (a - a.mean()) / (a.std() + 1e-6)
    b = (b - b.mean()) / (b.std() + 1e-6)
    return float((a * b).mean())


def same_picture_moved(a: np.ndarray, b: np.ndarray) -> tuple[int, float | None]:
    """두 회색 프레임이 '같은 그림이 자리·크기만 바뀐 것'인가 — ORB 짝 + 부분 아핀(RANSAC) 일치점 수와 배율.
    게시글형은 자막 줄이 늘면 그림 칸이 아래로 밀리거나 커진다(같은 장면). 바탕 빼기 상관은 이걸 컷으로 본다."""
    orb = cv2.ORB_create(800)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 10 or len(kb) < 10:
        return 0, None
    ms = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(ms) < 8:
        return 0, None
    pa = np.float32([ka[m.queryIdx].pt for m in ms])
    pb = np.float32([kb[m.trainIdx].pt for m in ms])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if M is None:
        return 0, None
    return int(inl.sum()), round(float(np.hypot(M[0, 0], M[0, 1])), 3)


def cut_verify(path: str, window: list[int], cands: list[float], fps: float,
               bg: float | None = None, info: dict | None = None) -> tuple[list[float], list]:
    """컷 앞(k−1)·뒤(k+1) 프레임의 창 위쪽 65% 64×64 z정규화 상관 < CUT_VERIFY_CORR 이면 진짜 컷.
    bg(배경 회색)를 주면 '두 프레임 다 배경색'인 화소를 빼고 재고(남는 화소 < CUT_VERIFY_ACTIVE_MIN 이면 전체),
    그 바탕 빼기를 한 쌍(그림 칸이 창 안에 뜬 inset 쌍)에 한해 상관이 낮아도 같은 그림이 자리·크기만 바뀐 것
    (same_picture_moved 일치점 ≥ CUT_MOVE_INLIERS, 배율 CUT_MOVE_SCALE 안)이면 컷이 아니다 — info["moved"] 에 [t, 일치점, 배율].
    창 안에 자막 줄이 함께 있으면 칸 테두리로는 이동을 못 본다(rGFX 원본 7.83: 상자 그대로·그림만 20px 아래) → 그림 일치로만 본다.
    한계: 칸 안에서 같은 그림을 당겨 찍은 편집 컷(펀치인)도 이동으로 본다."""
    if not cands:
        return [], []
    x, y, w, h = window
    hh = int(h * CUT_VERIFY_TOP)
    sig = [g.astype(np.float64).ravel() for g in probe.frames(path, f"crop={w}:{hh}:{x}:{y},scale=64:64", 64, 64, "gray")]
    big = {}
    if bg is not None:
        need = {int(round(t * fps)) + d for t in cands for d in (-1, 1)}
        sw = CUT_MOVE_W
        sh = max(2, int(round(sw * hh / w / 2) * 2))
        for i, g in enumerate(probe.frames(path, f"crop={w}:{hh}:{x}:{y},scale={sw}:{sh}", sw, sh, "gray")):
            if i in need:
                big[i] = g.copy()
    moved = []
    keep, corr = [], []
    for t in cands:
        k = int(round(t * fps))
        if k - 1 < 0 or k + 1 >= len(sig):
            keep.append(t); corr.append(None)
            continue
        A, B = sig[k - 1], sig[k + 1]
        m = None
        if bg is not None:
            m = (np.abs(A - bg) > CUT_BG_TOL) | (np.abs(B - bg) > CUT_BG_TOL)
            if m.mean() < CUT_VERIFY_ACTIVE_MIN or not inset(m.reshape(64, 64)):
                m = None
        c = _zcorr(A, B) if m is None else _zcorr(A[m], B[m])
        corr.append(round(c, 3))
        if c >= CUT_VERIFY_CORR:
            continue
        if m is not None and k - 1 in big and k + 1 in big:
            n, sc = same_picture_moved(big[k - 1], big[k + 1])
            if n >= CUT_MOVE_INLIERS and sc is not None and CUT_MOVE_SCALE[0] <= sc <= CUT_MOVE_SCALE[1]:
                moved.append([t, n, sc])
                continue
        keep.append(t)
    if info is not None:
        info["moved"] = moved
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
    bg = window_bg(path, win) if bg_gray(vl) is not None else None   # 틀(바탕)이 있는 편만, 바탕 값은 창 안에서
    raw = scene_detect(path, win)                      # 옛 자(희석 보정 없음) — raw_stats·기준선 재현용
    det = scene_detect(path, win, bg=bg, fps=meta["fps"]) if bg is not None else raw
    cands = merge_close(det)
    vinfo: dict = {}
    cuts, corr = cut_verify(path, win, cands, meta["fps"], bg=bg, info=vinfo)
    segs = shot_lengths(cuts, dur)
    eq, n = cut_eq_sub(cuts, sub_changes) if sub_changes else (None, len(cuts))
    gaps = still_gaps(cuts, sub_changes, dur)
    raw_segs = shot_lengths(raw, dur)
    # 병합·검증 전(scene>T 그대로)의 값 — 옛 자(cuts.py·rhythm_stats, 함수 지도 §1-B)와 같은 정의라 기준선 재현 확인용
    raw_stats = {"shots": len(raw) + 1, "first_cut": round(raw_segs[0], 2), "cut_std": round(st.pstdev(raw_segs), 2),
                 "cut_eq_sub": list(cut_eq_sub(raw, sub_changes)) if sub_changes else None}
    res = {"scene_t": C.SCENE_T, "raw": raw, "raw_stats": raw_stats, "candidates": cands, "corr": corr, "cuts": cuts,
           "bg_gray": None if bg is None else round(bg, 1), "detected": det, "moved": vinfo.get("moved", []),
           "merged_out": [t for t in det if t not in cands],
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
