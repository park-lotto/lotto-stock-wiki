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
from .constants import (CAP_FPS, CAP_SCALE_W, CAP_SCALE_H, CAP_DIFF, CAP_MERGE_S, CAP_STILL, CAP_BAND_PAD, CAPTION_INSET,
                        LINE_ROW_FRAC, LINE_MIN_H, FILL_LUM, FILL_CHROMA, FILL_BG_DIFF, FILL_FRAC,
                        GLYPH_RUN_MAX, GLYPH_FIRST_LINE_MIN, GLYPH_ROW_PX, GLYPH_OUTLINE_DIFF, GLYPH_PER_VIDEO,
                        GLYPH_SHADOW_DROP, GLYPH_SHADOW_FRAC, ANIM_FRAMES, ANIM_W_FRAC, ANIM_CX_PX, ANIM_AREA,
                        BAND_PRESENCE, INSIDE_PRESENCE, SEG_GAP, CAP_SPAN_OK, CAP_BAND_MAX_FRAC, CAP_PERSIST_LAG)


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
def caption_track(path: str, vl: dict, duration: float) -> dict:
    """자막 교체 시각·자막 구간·흔들림 구간 — 교체 판단의 주인(caption_changes·measure_video 가 이것을 부른다).

    1) 띠를 540×100으로 줄여 CAP_FPS로 잉크 XOR 평균 d > CAP_DIFF 인 프레임 = 바뀜 후보, CAP_MERGE_S 병합.
    2) 후보 사이 구간마다 안쪽 프레임 d 의 중앙값 > CAP_STILL 이면 '흔들림'(글자가 아니라 영상이 띠에 비침)
       → 자막 구간에서 빼고, 앞뒤 구간이 둘 다 흔들림인 후보는 교체에서도 뺀다(흔들림 시작·끝 시각은 남는다).
    반환: {"changes": [초…], "spans": [(시작, 끝)…](흔들림 제외), "unstable": [[시작, 끝]…](이어진 것끼리 합침)}"""
    reg = caption_region(vl)
    if not reg:
        return {"changes": [], "spans": [], "unstable": []}
    y0, y1 = reg
    W = vl["canvas"][0]
    vf = f"fps={CAP_FPS},crop={W}:{y1 - y0}:0:{y0},scale={CAP_SCALE_W}:{CAP_SCALE_H}"
    pol = vl["caption"]["ink"]
    prev = None
    d: list[float] = []
    for f in probe.frames(path, vf, CAP_SCALE_W, CAP_SCALE_H):
        ink = ink_mask(f, pol)
        d.append(float((ink ^ prev).mean()) if prev is not None else 0.0)
        prev = ink
    cand: list[float] = []
    for k, x in enumerate(d):
        t = k / CAP_FPS
        if x > CAP_DIFF and t < duration and (not cand or t - cand[-1] > CAP_MERGE_S):
            cand.append(round(t, 2))
    bounds = [0.0] + cand + [duration]
    still = []
    for a, e in zip(bounds, bounds[1:]):
        inside = d[int(round(a * CAP_FPS)) + 1:int(round(e * CAP_FPS))]
        if inside:
            still.append(float(np.median(inside)) <= CAP_STILL)
        else:  # 안쪽 프레임이 없는 끝 조각(0.1초)은 잴 수 없다 → 바로 앞 구간을 따른다
            still.append(still[-1] if still else True)
    changes = [t for i, t in enumerate(cand) if still[i] or still[i + 1]]
    spans = [(a, e) for (a, e), s in zip(zip(bounds, bounds[1:]), still) if s]
    unstable: list[list[float]] = []
    for (a, e), s in zip(zip(bounds, bounds[1:]), still):
        if not s:
            if unstable and abs(unstable[-1][1] - a) < 1e-6:
                unstable[-1][1] = e
            else:
                unstable.append([a, e])
    return {"changes": changes, "spans": spans, "unstable": [[round(a, 2), round(e, 2)] for a, e in unstable]}


def caption_changes(path: str, vl: dict, duration: float) -> list[float]:
    """자막 교체 시각(첫 자막 시작 0 제외) — caption_track 의 changes."""
    return caption_track(path, vl, duration)["changes"]


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
    tr = caption_track(path, vl, dur)
    changes, spans = tr["changes"], tr["spans"]
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
            "unstable": tr["unstable"], "items": items, "glyph": glyph}


# ── 편 하나: 자막 띠 고르기 ────────────────────────────────────────────────
# layout._caption 은 "창 위/아래에 자주 바뀌는 행이 10행만 있어도 그쪽"이라 편 하나에선 머리띠(고정 제목)를 자막으로
# 고를 때가 있다(2026-10-16 썰풀다). 편 하나를 잴 때(칼카피 analyze·compare)는 후보 띠를 여럿 세워 실제로 재 보고 고른다.
def band_candidates(vl: dict, presence: dict, extra: list[dict] | None = None) -> list[dict]:
    """후보 띠: layout 이 고른 것 + 창 위/아래(BAND_PRESENCE)·안(INSIDE_PRESENCE) × 극성 2 의 잉크 행 덩어리.
    presence = layout.measure_video 의 `_presence`(극성별 '행에 잉크 있음' 표본 비율)."""
    win = vl["window"]
    H = vl["canvas"][1]
    wy0, wy1 = win[1], win[1] + win[3]
    regions = {"above": (0, max(0, wy0 - CAPTION_INSET), BAND_PRESENCE),
               "below": (min(H, wy1 + CAPTION_INSET), H, BAND_PRESENCE),
               "inside": (wy0, wy1, INSIDE_PRESENCE)}
    out = [dict(c) for c in ([vl.get("caption")] + list(extra or [])) if c and c.get("band")]
    for pos, (a, b, thr) in regions.items():
        if b - a < LINE_MIN_H:
            continue
        for pol in ("dark", "bright"):
            for s0, e0 in segs(presence[pol][a:b] >= thr, min_len=LINE_MIN_H // 2, gap=SEG_GAP * 4):
                if e0 - s0 <= CAP_BAND_MAX_FRAC * H:
                    out.append({"pos": pos, "band": [int(s0 + a), int(e0 + a)], "ink": pol})
    uniq: list[dict] = []
    for c in out:
        if not any(u["pos"] == c["pos"] and u["ink"] == c["ink"] and abs(u["band"][0] - c["band"][0]) <= 8
                   and abs(u["band"][1] - c["band"][1]) <= 8 for u in uniq):
            uniq.append(c)
    return uniq


def persistence(path: str, vl: dict) -> dict:
    """띠 잉크가 CAP_PERSIST_LAG 표본(0.3초) 뒤에도 그 자리에 남는 비율(중앙값)·잉크가 보이는 표본 비율.
    자막은 바뀌기 전까지 가만히 있어 ~1.0, 영상 속 밝은 모서리는 움직여 ~0 (2026-10-15 썰풀다 실측 1.0 vs 0.0)."""
    reg = caption_region(vl)
    if not reg:
        return {"persist": 0.0, "coverage": 0.0}
    y0, y1 = reg
    W = vl["canvas"][0]
    fr = [ink_mask(f, vl["caption"]["ink"]) for f in
          probe.frames(path, f"fps={CAP_FPS},crop={W}:{y1 - y0}:0:{y0},scale={CAP_SCALE_W}:{CAP_SCALE_H}", CAP_SCALE_W, CAP_SCALE_H)]
    v = [(a & b).sum() / a.sum() for a, b in zip(fr, fr[CAP_PERSIST_LAG:]) if a.sum() > 30]
    return {"persist": round(float(np.median(v)), 3) if v else 0.0,
            "coverage": round(float(np.mean([a.sum() > 30 for a in fr])), 3) if fr else 0.0}


def caption_score(cap: dict, pers: dict) -> float:
    """자막다운 구간 수(길이 CAP_SPAN_OK 안 + 가운데 프레임에 줄 1~3개) × 잉크 지속도 × 잉크 보이는 비율."""
    n = sum(1 for it in cap.get("items", []) if CAP_SPAN_OK[0] <= it["t1"] - it["t0"] <= CAP_SPAN_OK[1]
            and 1 <= it.get("lines", 0) <= 3)
    return round(n * pers["persist"] * pers["coverage"], 2)


def tighten_band(path: str, vl: dict, cap: dict) -> list[int] | None:
    """고른 띠를 **실제 글자 행**으로 좁힌다: 자막 구간(흔들림 제외)마다 가운데 프레임의 잉크 행(> GLYPH_ROW_PX)을 합친 범위.
    띠 후보는 표본 비율로 잡혀 엔딩·영상이 비친 행까지 넓어진다(2026-10-16 ZdeZRtCeAC4 [1438,1920] → 글자 ≈1466~1529)."""
    reg = caption_region(vl)
    if not reg or not cap.get("items"):
        return None
    y0, y1 = reg
    W = vl["canvas"][0]
    rows = np.zeros(y1 - y0, bool)
    for it in cap["items"]:
        if it.get("lines", 0) < 1:
            continue
        img = probe.grab(path, (it["t0"] + it["t1"]) / 2, f"crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0)
        if img is not None:
            rows |= ink_mask(img, vl["caption"]["ink"]).sum(axis=1) > GLYPH_ROW_PX
    runs = segs(rows, min_len=GLYPH_FIRST_LINE_MIN, gap=SEG_GAP * 4)
    if not runs:
        return None
    return [int(runs[0][0] + y0), int(runs[-1][1] + y0)]


def choose_caption(path: str, vl: dict, meta: dict, presence: dict, extra: list[dict] | None = None) -> dict:
    """후보 띠마다 measure_video + persistence → 점수 최고(같으면 좁은 띠). 반환 {caption, result, scored}.
    점수가 모두 0이면 caption = layout 이 고른 것, result = None."""
    scored, best = [], None
    for c in band_candidates(vl, presence, extra):
        v = {**vl, "caption": c}
        try:
            cap = measure_video(path, v, meta)
        except Exception as e:  # noqa: BLE001 — 후보 하나 실패는 표에 남긴다
            scored.append({**c, "score": None, "failed": f"{type(e).__name__}: {str(e)[:80]}"})
            continue
        pers = persistence(path, v)
        s = caption_score(cap, pers)
        scored.append({**c, "score": s, "spans": len(cap["spans"]), **pers})
        h = c["band"][1] - c["band"][0]
        if best is None or s > best[0] or (s == best[0] and h < best[3]):
            best = (s, c, cap, h)
    if best and best[0] > 0:
        c, cap = best[1], best[2]
        tb = tighten_band(path, {**vl, "caption": c}, cap)
        if tb and (tb[1] - tb[0]) < (c["band"][1] - c["band"][0]):
            c2 = {**c, "band": tb, "band_before_tighten": c["band"]}
            cap = measure_video(path, {**vl, "caption": c2}, meta)
            c = c2
        return {"caption": c, "result": cap, "scored": scored}
    return {"caption": vl.get("caption"), "result": None, "scored": scored}


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
