# -*- coding: utf-8 -*-
"""captions — S.* T.sub_*  자막의 교체 시각·줄·폭·시작 y·형광펜·획·외곽선·그림자·등장 효과.

좌표는 전부 layout(편별 `video_layout`)에서 온다: 자막 자리(위/아래/안)·띠 행·잉크 극성·배경색.
잉크 판정은 layout.ink_mask 하나(극성별 문턱 110/200)만 쓴다.
옮겨 온 자(함수 지도 §1-B 옛 측정 스크립트): cuts.py(교체)·lines.py(줄·폭·y·형광펜)·glyph_style.py(획·높이·외곽선·그림자·등장).
"""
from __future__ import annotations

import statistics as st

import numpy as np
import cv2

from . import probe
from .layout import ink_mask, lum, segs
from .constants import (CAP_FPS, CAP_SCALE_W, CAP_SCALE_H, CAP_DIFF, CAP_MERGE_S, CAP_BAND_PAD, CAPTION_INSET,
                        LINE_ROW_FRAC, LINE_MIN_H, FILL_LUM, FILL_CHROMA, FILL_BG_DIFF, FILL_FRAC,
                        GLYPH_RUN_MAX, GLYPH_FIRST_LINE_MIN, GLYPH_ROW_PX, GLYPH_OUTLINE_DIFF, GLYPH_PER_VIDEO,
                        GLYPH_SHADOW_DROP, GLYPH_SHADOW_FRAC, ANIM_FRAMES, ANIM_W_FRAC, ANIM_CX_PX, ANIM_AREA)


def caption_region(vl: dict) -> tuple[int, int] | None:
    """재는 행 범위 [y0, y1). 자막 띠 ± CAP_BAND_PAD, 영상창 안(아래/위 자리일 때)은 넘지 않는다."""
    cap = vl["caption"]
    if not cap or not cap.get("band"):
        return None
    H = vl["canvas"][1]
    wx, wy, ww, wh = vl["window"]
    b0, b1 = cap["band"]
    y0, y1 = b0 - CAP_BAND_PAD, b1 + CAP_BAND_PAD
    if cap["pos"] == "below":
        y0 = max(y0, wy + wh + CAPTION_INSET)
    elif cap["pos"] == "above":
        y1 = min(y1, wy - CAPTION_INSET)
    else:  # inside
        y0, y1 = max(y0, wy), min(y1, wy + wh)
    y0, y1 = max(0, y0), min(H, y1)
    return (int(y0), int(y1)) if y1 - y0 >= LINE_MIN_H else None


# ── 교체 시각 ──────────────────────────────────────────────────────────────
def caption_changes(path: str, vl: dict, duration: float) -> list[float]:
    """자막 교체 시각(첫 자막 시작 0 제외). 띠를 540×100으로 줄여 CAP_FPS로 잉크 XOR 평균 > CAP_DIFF, CAP_MERGE_S 병합."""
    reg = caption_region(vl)
    if not reg:
        return []
    y0, y1 = reg
    W = vl["canvas"][0]
    vf = f"fps={CAP_FPS},crop={W}:{y1 - y0}:0:{y0},scale={CAP_SCALE_W}:{CAP_SCALE_H}"
    pol = vl["caption"]["ink"]
    prev = None
    ch = []
    for k, f in enumerate(probe.frames(path, vf, CAP_SCALE_W, CAP_SCALE_H)):
        ink = ink_mask(f, pol)
        if prev is not None and (ink ^ prev).mean() > CAP_DIFF:
            ch.append(k / CAP_FPS)
        prev = ink
    out: list[float] = []
    for t in ch:
        if t < duration and (not out or t - out[-1] > CAP_MERGE_S):
            out.append(round(t, 2))
    return out


def caption_spans(changes: list[float], duration: float) -> list[tuple[float, float]]:
    """교체 시각 → 자막 구간 [(시작, 끝)]. 첫 자막은 0초에서 시작한다."""
    starts = [0.0] + changes
    ends = changes + [duration]
    return list(zip(starts, ends))


# ── 한 장면(자막 한 개) 재기 ────────────────────────────────────────────────
def is_fill(img: np.ndarray, bg_rgb: list[int]) -> np.ndarray:
    """형광펜(글자 뒤 채움) 화소: 밝고 채도 있고 배경색과 다르다. 특정 색 고정값을 안 쓴다."""
    a = img.astype(np.int16)
    chroma = a.max(axis=2) - a.min(axis=2)
    diff = np.abs(a - np.array(bg_rgb, np.int16)[None, None, :]).max(axis=2)
    return (lum(img) > FILL_LUM) & (chroma > FILL_CHROMA) & (diff > FILL_BG_DIFF)


def caption_lines(img: np.ndarray, pol: str, y_off: int, bg_rgb: list[int]) -> dict | None:
    """줄 수·줄별 잉크 폭·첫 줄 y·행간·형광펜. 줄 = 행 잉크 비율 > LINE_ROW_FRAC 가 LINE_MIN_H행 이상."""
    ink = ink_mask(img, pol)
    bands = segs(ink.mean(axis=1) > LINE_ROW_FRAC, min_len=LINE_MIN_H)
    if not bands:
        return None
    widths = []
    for s0, e0 in bands:
        xs = np.where(ink[s0:e0].any(axis=0))[0]
        widths.append(int(xs.max() - xs.min()))
    return {"lines": len(bands), "widths": widths, "top_y": int(bands[0][0] + y_off),
            "leading": int(bands[1][0] - bands[0][0]) if len(bands) > 1 else None,
            "mark": bool(is_fill(img, bg_rgb).mean() > FILL_FRAC)}


def _run_median(mask: np.ndarray) -> float | None:
    out = []
    for row in mask:
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        s = np.where(d == 1)[0]; e = np.where(d == -1)[0]
        out.extend(int(x) for x in (e - s) if x < GLYPH_RUN_MAX)
    return float(st.median(out)) if out else None


def glyph_style(img: np.ndarray, pol: str, bg_rgb: list[int]) -> dict | None:
    """획 폭(잉크 가로/세로 연속길이 중앙값 중 작은 쪽)·첫 줄 높이·외곽선·그림자 (glyph_style 정의)."""
    L = lum(img)
    ink = ink_mask(img, pol)
    if ink.sum() < 50:
        return None
    rows = ink.sum(axis=1) > GLYPH_ROW_PX
    first = segs(rows, min_len=GLYPH_FIRST_LINE_MIN)
    if not first:
        return None
    y0, y1 = first[0]
    sub = ink[y0:y1]
    sw = [x for x in (_run_median(sub), _run_median(sub.T)) if x]
    bg_l = float(0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2])
    ring = cv2.dilate(ink.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~ink
    ring_l = float(L[ring].mean()) if ring.any() else None
    outline = bool(ring_l is not None and abs(ring_l - bg_l) > GLYPH_OUTLINE_DIFF
                   and abs(ring_l - float(L[ink].mean())) > GLYPH_OUTLINE_DIFF)
    shadow_px = (np.abs(L - bg_l) > GLYPH_SHADOW_DROP) & ~ink
    shadow = None
    for dy in range(2, 7):
        for dx in range(-6, 7, 2):
            sh = np.roll(np.roll(ink, dy, 0), dx, 1) & ~ink
            if sh.sum() and (shadow_px & sh).sum() / sh.sum() > GLYPH_SHADOW_FRAC:
                shadow = [dx, dy]
                break
        if shadow:
            break
    return {"line_h": int(y1 - y0), "stroke": min(sw) if sw else None, "outline": outline, "shadow": shadow}


def _ink_box(mask: np.ndarray):
    ys, xs = np.where(mask)
    if len(ys) < 50:
        return None
    return int(xs.min()), int(xs.max()), int(mask.sum())


def caption_anim(path: str, vl: dict, t0: float, fps: float) -> str:
    """등장 효과: 자막 시작 뒤 ANIM_FRAMES 프레임의 잉크 bbox 폭·중심·면적 변화."""
    reg = caption_region(vl)
    W = vl["canvas"][0]
    y0, y1 = reg
    pol = vl["caption"]["ink"]
    seq = [b for b in (_ink_box(ink_mask(f, pol)) for f in
                       probe.frames(path, f"crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0, ss=t0, dur=ANIM_FRAMES / fps))
           if b]
    if len(seq) < 4:
        return "판정불가"
    w = [b[1] - b[0] for b in seq]; cx = [(b[0] + b[1]) / 2 for b in seq]; area = [b[2] for b in seq]
    if abs(w[-1] - w[0]) / max(w[-1], 1) > ANIM_W_FRAC:
        return "확대/축소"
    if abs(cx[-1] - cx[0]) > ANIM_CX_PX:
        return "이동"
    if area[0] < ANIM_AREA * area[-1]:
        return "페이드/타자기"
    return "없음"


# ── 편 하나 ────────────────────────────────────────────────────────────────
def measure_video(path: str, vl: dict, meta: dict) -> dict:
    """편 하나의 자막 측정. 자막 자리를 못 찾은 편은 caption=None으로 돌려준다(멈추지 않는다)."""
    reg = caption_region(vl)
    if not reg:
        return {"region": None, "changes": [], "spans": [], "items": [], "glyph": []}
    dur = meta["duration"]
    changes = caption_changes(path, vl, dur)
    spans = caption_spans(changes, dur)
    y0, y1 = reg
    W = vl["canvas"][0]
    pol = vl["caption"]["ink"]
    want = {int(round((a + b) / 2 * CAP_FPS)): i for i, (a, b) in enumerate(spans)}
    mids: dict[int, np.ndarray] = {}
    for k, f in enumerate(probe.frames(path, f"fps={CAP_FPS},crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0)):
        if k in want:
            mids[want[k]] = f.copy()
    items = []
    for i, (a, b) in enumerate(spans):
        img = mids.get(i)
        m = caption_lines(img, pol, y0, vl["bg_rgb"]) if img is not None else None
        items.append({"i": i, "t0": round(a, 2), "t1": round(b, 2), **(m or {"lines": 0})})
    glyph = []
    for i in sorted(set(np.linspace(0, len(spans) - 1, min(GLYPH_PER_VIDEO, len(spans))).astype(int).tolist())):
        img = mids.get(i)
        g = glyph_style(img, pol, vl["bg_rgb"]) if img is not None else None
        if g:
            g["i"] = i
            g["anim"] = caption_anim(path, vl, spans[i][0] + 0.03, meta["fps"])
            glyph.append(g)
    return {"region": [y0, y1], "changes": changes, "spans": [[round(a, 2), round(b, 2)] for a, b in spans],
            "items": items, "glyph": glyph}


# ── 채널 기준 ──────────────────────────────────────────────────────────────
def _dist(a: list[float], k: int = 2) -> dict:
    a = np.array(a, float)
    return {"value": round(float(np.median(a)), k), "stat": "median", "range": [round(float(a.min()), k), round(float(a.max()), k)],
            "p10": round(float(np.percentile(a, 10)), k), "p90": round(float(np.percentile(a, 90)), k), "n": int(len(a))}


def summarize(per_video: dict[str, dict], vids: list[str]) -> dict:
    """main 틀 영상들의 자막 기준. 각 기준의 method = 잰 함수."""
    got = [(v, per_video[v]["captions"]) for v in vids if per_video[v].get("captions", {}).get("region")]
    if not got:
        return {}
    items = [it for _, c in got for it in c["items"] if it.get("lines", 0) > 0]
    crit = {}
    crit["T.sub_count"] = {**_dist([len(c["spans"]) for _, c in got], 0), "unit": "개/편",
                           "total": sum(len(c["spans"]) for _, c in got), "method": "captions.caption_changes"}
    crit["T.sub_sec"] = {**_dist([b - a for _, c in got for a, b in c["spans"]], 2), "unit": "초",
                         "per_video_median": {v: round(float(np.median([b - a for a, b in c["spans"]])), 2) for v, c in got},
                         "method": "captions.caption_spans"}
    hist = {}
    for it in items:
        hist[str(it["lines"])] = hist.get(str(it["lines"]), 0) + 1
    crit["S.lines"] = {"value": hist, "stat": "hist", "n": len(items), "unit": "줄", "method": "captions.caption_lines"}
    ws = [w for it in items for w in it["widths"]]
    crit["S.line_w"] = {"value": int(np.median(ws)), "stat": "median", "p90": int(np.percentile(ws, 90)), "max": int(max(ws)),
                        "n": len(ws), "unit": "px", "method": "captions.caption_lines"}
    crit["L.sub_top"] = {**_dist([it["top_y"] for it in items], 0), "unit": "px", "method": "captions.caption_lines"}
    lead = [it["leading"] for it in items if it.get("leading")]
    if lead:
        crit["S.leading"] = {**_dist(lead, 0), "unit": "px", "method": "captions.caption_lines"}
    marks = [it for it in items if it.get("mark")]
    firsts = [c["items"][0] for _, c in got if c["items"]]
    lasts = [c["items"][-1] for _, c in got if c["items"]]
    crit["S.mark_rate"] = {"value": round(len(marks) / len(items), 3), "stat": "ratio", "count": len(marks), "n": len(items),
                           "method": "captions.is_fill"}
    crit["S.mark_first"] = {"value": sum(1 for it in firsts if it.get("mark")), "stat": "count", "n": len(firsts),
                            "method": "captions.is_fill"}
    crit["S.mark_last"] = {"value": sum(1 for it in lasts if it.get("mark")), "stat": "count", "n": len(lasts),
                           "method": "captions.is_fill"}
    gl = [g for _, c in got for g in c["glyph"]]
    if gl:
        pv_stroke = [st.median([g["stroke"] for g in c["glyph"] if g["stroke"]]) for _, c in got if c["glyph"]]
        pv_h = [st.median([g["line_h"] for g in c["glyph"]]) for _, c in got if c["glyph"]]
        crit["S.weight"] = {"value": float(st.median(pv_stroke)), "stat": "median of per-video median",
                            "range": [min(pv_stroke), max(pv_stroke)], "n": len(gl), "unit": "px", "method": "captions.glyph_style"}
        crit["S.size_px"] = {"value": float(st.median(pv_h)), "stat": "median of per-video median",
                             "range": [min(pv_h), max(pv_h)], "n": len(gl), "unit": "px", "method": "captions.glyph_style"}
        crit["S.outline"] = {"value": sum(1 for g in gl if g["outline"]), "stat": "count", "n": len(gl), "method": "captions.glyph_style"}
        crit["S.shadow"] = {"value": sum(1 for g in gl if g["shadow"]), "stat": "count", "n": len(gl), "method": "captions.glyph_style"}
        an = {}
        for g in gl:
            an[g["anim"]] = an.get(g["anim"], 0) + 1
        crit["S.anim"] = {"value": an, "stat": "hist", "n": len(gl), "method": "captions.caption_anim"}
    return crit
