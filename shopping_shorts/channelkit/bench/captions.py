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
from .layout import ink_mask, ink_fill, lum, segs
from .constants import (CAP_FPS, CAP_SCALE_W, CAP_SCALE_H, CAP_DIFF, CAP_MERGE_S, CAP_CORE_MIN_PX, CAP_CORE_KEEP,
                        CAP_CORE_SAME, CAP_CORE_MAX_FRAC, CAP_STILL, CAP_BAND_PAD, CAPTION_INSET,
                        LINE_ROW_FRAC, LINE_MIN_H, FILL_LUM, FILL_CHROMA, FILL_BG_DIFF, FILL_FRAC,
                        GLYPH_RUN_MAX, GLYPH_FIRST_LINE_MIN, GLYPH_ROW_PX, GLYPH_OUTLINE_DIFF, GLYPH_PER_VIDEO,
                        GLYPH_SHADOW_DROP, GLYPH_SHADOW_FRAC, GLYPH_SHADOW_ASYM, ANIM_FRAMES, ANIM_W_FRAC, ANIM_CX_PX, ANIM_AREA,
                        BAND_PRESENCE, INSIDE_PRESENCE, SEG_GAP, CAP_SPAN_OK, CAP_BAND_MAX_FRAC, CAP_PERSIST_LAG,
                        CAP_MIN_SCORE, CAP_TIGHT_GAP, CAP_TIGHT_REL, CAP_TIE_FRAC, CAP_SUB_STEPS, CAP_SUB_MAX_FRAC, CAP_LOW_PRESENCE, CAP_STATIC_MAX, CAP_STATIC_MIN_SPANS, CAP_POL_TIE, CAP_FILL_BRIGHT, INK_DARK, CAP_FREE_PAD, CAP_EXTEND_LINES, CAP_LINE_CHANGE, CAP_EXTEND_DT, CAP_EXTEND_STEADY, CAP_EXTEND_SHARE, INK_BRIGHT, INK_OUTLINE_DARK)


def caption_region(vl: dict) -> tuple[int, int] | None:
    """재는 행 범위 [y0, y1). 자막 띠 ± CAP_BAND_PAD, 영상창 안(아래/위 자리일 때)은 넘지 않는다.
    caption["free"] 이면 창 경계로 자르지 않는다 — 누적형 자막이 창 위로 넘어 3줄째가 창에 걸칠 때(extend_band)."""
    cap = vl["caption"]
    if not cap or not cap.get("band"):
        return None
    H = vl["canvas"][1]
    wx, wy, ww, wh = vl["window"]
    b0, b1 = cap["band"]
    pad = CAP_FREE_PAD if cap.get("free") else CAP_BAND_PAD   # 넓힌 띠는 이미 글자 줄 단위 — 넉넉히 두면 창 속 영상이 섞인다
    y0, y1 = b0 - pad, b1 + pad
    if cap.get("free"):
        pass
    elif cap["pos"] == "below":
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
    2) 후보 사이 조각마다 '글자 심지'(조각 프레임의 절반 이상에 찍힌 잉크)를 만들고, 심지가 CAP_CORE_MIN_PX 이상이며
       프레임들이 심지를 평균 CAP_CORE_KEEP 이상 덮으면 '가만히 있는 글자'(자막 조각), 아니면 '흔들림'(영상이 띠에 비침).
       1판(faf9ca750)은 조각 안 XOR 중앙값 ≤ CAP_STILL 로 갈라, 움직이는 영상 위 자막(창 안 흰 글자)까지 흔들림으로 버렸다
       (2026-10-16 썰풀다 mYxuF1A74j4 자막 19→8, 핫템 a06y 1/3만). 글자 아닌 화소가 바뀌는 것은 심지에 안 들어가 무관하다.
    3) 이웃한 자막 조각의 심지가 CAP_CORE_SAME 이상 겹치면 같은 자막 하나로 잇는다(영상 출렁임에 쪼개진 것).
    반환: {"changes": [초…], "spans": [(시작, 끝)…](흔들림 제외), "unstable": [[시작, 끝]…](이어진 것끼리 합침)}"""
    reg = caption_region(vl)
    if not reg:
        return {"changes": [], "spans": [], "unstable": []}
    y0, y1 = reg
    W = vl["canvas"][0]
    vf = f"fps={CAP_FPS},crop={W}:{y1 - y0}:0:{y0},scale={CAP_SCALE_W}:{CAP_SCALE_H}"
    pol = vl["caption"]["ink"]
    masks = [ink_mask(f, pol) for f in probe.frames(path, vf, CAP_SCALE_W, CAP_SCALE_H)]
    d = [0.0] + [float((m ^ p_).mean()) for p_, m in zip(masks, masks[1:])]
    cand: list[float] = []
    for k, x in enumerate(d):
        t = k / CAP_FPS
        if x > CAP_DIFF and t < duration and (not cand or t - cand[-1] > CAP_MERGE_S):
            cand.append(round(t, 2))
    bounds = [0.0] + cand + [duration]
    pieces = []          # [시작, 끝, 가만?, 심지]
    pending = None       # 맨 앞 0.1초 조각(인코더 첫 프레임 흔들림 — 1판 '첫 자막 0.0~0.1초')을 다음 조각 시작으로
    for a_, e_ in zip(bounds, bounds[1:]):
        fr = masks[int(round(a_ * CAP_FPS)) + 1:int(round(e_ * CAP_FPS))]
        if len(fr) < 2:  # 안쪽 프레임이 거의 없는 조각(0.1초)은 잴 수 없다 → 이웃 조각에 붙인다(앞이 없으면 뒤에)
            if pieces:
                pieces[-1][1] = e_
            else:
                pending = a_
            continue
        if pending is not None:
            a_, pending = pending, None
        core = np.mean(fr, axis=0) >= 0.5
        n = int(core.sum())
        keep = float(np.mean([(m & core).sum() / n for m in fr])) if n else 0.0
        # 심지가 띠를 CAP_CORE_MAX_FRAC 넘게 덮으면서 조각 안 XOR 중앙값도 CAP_STILL 를 넘으면 움직이는 영상(엔딩 전체화면 얼굴 등).
        # 큰 굵은 자막은 띠의 17%를 덮지만 XOR≈0 이라 글자다(2026-10-16 bench 기준선 10편: 넓이만 보면 자막 232→203).
        moving = n > CAP_CORE_MAX_FRAC * core.size and float(np.median(d[int(round(a_ * CAP_FPS)) + 1:int(round(e_ * CAP_FPS))])) > CAP_STILL
        pieces.append([a_, e_, n >= CAP_CORE_MIN_PX and keep >= CAP_CORE_KEEP and not moving, core])
    merged = []
    for pc in pieces:
        if merged and pc[2] and merged[-1][2] and pc[3] is not None and merged[-1][3] is not None:
            c0, c1 = merged[-1][3], pc[3]
            if (c0 & c1).sum() / max(1, (c0 | c1).sum()) >= CAP_CORE_SAME:
                merged[-1][1] = pc[1]
                continue
        if merged and not pc[2] and not merged[-1][2]:
            merged[-1][1] = pc[1]
            continue
        merged.append(list(pc))
    spans = [(round(a_, 2), round(e_, 2)) for a_, e_, st_, _ in merged if st_]
    changes = [round(merged[i][0], 2) for i in range(1, len(merged)) if merged[i][2] or merged[i - 1][2]]
    unstable = [[round(a_, 2), round(e_, 2)] for a_, e_, st_, _ in merged if not st_]
    return {"changes": changes, "spans": spans, "unstable": unstable}


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
    """획 폭(잉크 가로/세로 연속길이 중앙값 중 작은 쪽)·첫 줄 높이·외곽선(두께)·그림자 (glyph_style 정의).
    잉크 = ink_fill(밝은 글자는 속까지 채움) — 테두리 고리만으로 재면 획 2px·외곽선 없음으로 나왔다(2026-10-16)."""
    L = lum(img)
    ink = ink_fill(img, pol)
    if ink.sum() < 50:
        return None
    rows = ink.sum(axis=1) > GLYPH_ROW_PX
    first = segs(rows, min_len=GLYPH_FIRST_LINE_MIN)
    if not first:
        return None
    y0, y1 = first[0]
    sub = ink[y0:y1]
    sw = [x for x in (_run_median(sub), _run_median(sub.T)) if x]
    # 바탕 밝기 = 글자에서 9~15px 떨어진 고리(그 자리 실제 바탕). 화면 배경색(bg_rgb)은 창 안 자막이면 영상과 다르다
    # (2026-10-16 썰풀다: 검은 바탕 편의 영상 위 흰 글자 굵은 검정 외곽선이 '외곽선 없음'으로 나옴). 고리를 못 재면 bg_rgb.
    def dil(r):
        return cv2.dilate(ink.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
    far = dil(15) & ~dil(9)
    bg_l = float(np.median(L[far])) if far.sum() > 50 else float(0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2])
    ink_l = float(L[ink].mean())
    ring = dil(3) & ~ink
    ring_l = float(L[ring].mean()) if ring.any() else None
    outline = bool(ring_l is not None and abs(ring_l - bg_l) > GLYPH_OUTLINE_DIFF and abs(ring_l - ink_l) > GLYPH_OUTLINE_DIFF)
    outline_px = 0
    if outline:          # 1px 고리마다 글자·바탕과 다르고 첫 고리와 같은 쪽인 동안 = 외곽선 두께
        prev = ink
        r1 = None
        for r in range(1, 13):
            d = dil(r)
            rr = d & ~prev
            prev = d
            if not rr.any():
                break
            l = float(np.median(L[rr]))
            r1 = l if r1 is None else r1
            if (abs(l - ink_l) > GLYPH_OUTLINE_DIFF and abs(l - bg_l) > GLYPH_OUTLINE_DIFF / 2
                    and (l - bg_l) * (r1 - bg_l) > 0):     # 글자와 다르고, 바탕과도 다르고, 첫 고리와 같은 쪽(어둡/밝)
                outline_px = r
            else:
                break
    # 그림자 = 한쪽으로만 치우친 어두운(밝은) 자리. 사방 외곽선은 모든 방향이 같아 그림자가 아니다 —
    # 1판은 외곽선이 있으면 첫 후보 [-6,2]가 늘 걸렸다(썰풀다 다섯 편 전부 [-6,2]).
    shadow_px = (np.abs(L - bg_l) > GLYPH_SHADOW_DROP) & ~ink

    def frac(dx, dy):
        sh = np.roll(np.roll(ink, dy, 0), dx, 1) & ~ink
        return (shadow_px & sh).sum() / sh.sum() if sh.sum() else 0.0
    shadow = None
    best = 0.0
    for dy in range(2, 7):
        for dx in range(-6, 7, 2):
            v = frac(dx, dy)
            asym = v - frac(-dx, -dy)
            if v > GLYPH_SHADOW_FRAC and asym > GLYPH_SHADOW_ASYM and asym > best:
                shadow, best = [dx, dy], asym
    return {"line_h": int(y1 - y0), "stroke": min(sw) if sw else None, "outline": outline, "outline_px": outline_px,
            "shadow": shadow}


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
def band_candidates(vl: dict, presence: dict, extra: list[dict] | None = None, row_lum=None) -> list[dict]:
    """후보 띠: layout 이 고른 것 + 창 위/아래(BAND_PRESENCE)·안(INSIDE_PRESENCE) × 극성 2 의 잉크 행 덩어리.
    presence = layout.measure_video 의 `_presence`(극성별 '행에 잉크 있음' 표본 비율).
    row_lum(행별 시간평균 밝기 중앙값)이 있으면 극성을 바탕으로 거른다: 흰 바탕(≥INK_BRIGHT)에선 bright 후보를 버린다 —
    검은 글자 옆 흰 바탕 화소가 'bright 잉크'(밝음+어두운 것 옆)로 잡혀 1등이 됐다(2026-10-16 방구석 ILIiqCJAOSI).
    검은 바탕(≤INK_OUTLINE_DARK)에선 dark 후보를 버린다."""
    win = vl["window"]
    H = vl["canvas"][1]
    wy0, wy1 = win[1], win[1] + win[3]
    regions = {"above": (0, max(0, wy0 - CAPTION_INSET), BAND_PRESENCE),
               "below": (min(H, wy1 + CAPTION_INSET), H, BAND_PRESENCE),
               "inside": (wy0, wy1, INSIDE_PRESENCE),
               # 장면마다 자리를 옮겨 다니는 창 안 자막은 한 행에 오래 머물지 않아 30% 문턱에 안 걸린다
               # (2026-10-16 썰풀다 7DYb y≈1067~1156 · w-Yg 반투명 상자 y≈1340~1440) → 낮은 문턱 후보도 세운다
               "inside_low": (wy0, wy1, CAP_LOW_PRESENCE)}
    out = [dict(c) for c in ([vl.get("caption")] + list(extra or [])) if c and c.get("band")]
    for pos_key, (a, b, thr) in regions.items():
        pos = "inside" if pos_key == "inside_low" else pos_key
        if b - a < LINE_MIN_H:
            continue
        for pol in ("dark", "bright"):
            runs = segs(presence[pol][a:b] >= thr, min_len=LINE_MIN_H, gap=SEG_GAP * 4)   # 글자 한 줄(21px)보다 얇은 띠는 영상 경계선(w-Yg 창 아래 끝 17px)
            for s0, e0 in runs:
                if e0 - s0 <= CAP_BAND_MAX_FRAC * H:
                    out.append({"pos": pos, "band": [int(s0 + a), int(e0 + a)], "ink": pol})
                else:
                    # 너무 넓은 덩어리(밝은 영상 위)는 문턱을 올려 가며 속의 짙은 줄 묶음을 후보로 꺼낸다
                    # (2026-10-16 w-Yg: 창 안 밝은 영상 때문에 자막 행 1330~1380 이 672px 넘는 덩어리에 묻혔다)
                    for up in CAP_SUB_STEPS:
                        for s1, e1 in segs(presence[pol][a + s0:a + e0] >= thr + up, min_len=LINE_MIN_H, gap=SEG_GAP):
                            if e1 - s1 <= CAP_SUB_MAX_FRAC * H:
                                out.append({"pos": pos, "band": [int(s1 + s0 + a), int(e1 + s0 + a)], "ink": pol})
            # 줄끼리 이은 후보: 이웃 줄 틈 ≤ 두 줄 중 큰 높이 — 누적형 자막의 1·2·3줄을 한 띠로(줄마다 따로면 덧붙는 순간을 못 센다)
            for i in range(len(runs)):
                j = i
                while j + 1 < len(runs) and runs[j + 1][0] - runs[j][1] <= max(runs[j][1] - runs[j][0], runs[j + 1][1] - runs[j + 1][0]):
                    j += 1
                    if runs[j][1] - runs[i][0] <= CAP_BAND_MAX_FRAC * H:
                        out.append({"pos": pos, "band": [int(runs[i][0] + a), int(runs[j][1] + a)], "ink": pol})
    if row_lum is not None:
        keep = []
        for c in out:
            m = float(np.median(row_lum[c["band"][0]:c["band"][1]]))
            if (c["ink"] == "bright" and m >= INK_BRIGHT) or (c["ink"] == "dark" and m <= INK_OUTLINE_DARK):
                continue
            keep.append(c)
        out = keep
    uniq: list[dict] = []
    for c in out:
        if not any(u["pos"] == c["pos"] and u["ink"] == c["ink"] and abs(u["band"][0] - c["band"][0]) <= 8
                   and abs(u["band"][1] - c["band"][1]) <= 8 for u in uniq):
            uniq.append(c)
    return uniq


def persistence(path: str, vl: dict, spans: list | None = None) -> dict:
    """띠 잉크가 CAP_PERSIST_LAG 표본(0.3초) 뒤에도 그 자리에 남는 비율(중앙값)·잉크가 보이는 표본 비율·글자 바뀜.
    자막은 바뀌기 전까지 가만히 있어 ~1.0, 영상 속 밝은 모서리는 움직여 ~0 (2026-10-15 썰풀다 실측 1.0 vs 0.0).
    change = 이웃 자막 구간 가운데 프레임끼리 잉크 1−IoU 의 중앙값. 고정 제목(영상 내내 같은 글자)은 ~0 —
    잉크 폭 출렁임을 교체로 세어 제목이 자막 1등이 됐다(2026-10-16 썰풀다 7DYbxVNz5q8 above [122,359] 점수 12)."""
    reg = caption_region(vl)
    if not reg:
        return {"persist": 0.0, "coverage": 0.0, "change": 0.0}
    y0, y1 = reg
    W = vl["canvas"][0]
    fr = [ink_mask(f, vl["caption"]["ink"]) for f in
          probe.frames(path, f"fps={CAP_FPS},crop={W}:{y1 - y0}:0:{y0},scale={CAP_SCALE_W}:{CAP_SCALE_H}", CAP_SCALE_W, CAP_SCALE_H)]
    v = [(a & b).sum() / a.sum() for a, b in zip(fr, fr[CAP_PERSIST_LAG:]) if a.sum() > 30]
    # 고정 글자 비율 = 영상 내내(표본 90% 이상) 찍힌 잉크 ÷ 평균 잉크. 창 위 끝에 걸친 제목 줄은 자막처럼 '바뀜'이 나와도
    # 글자 자체는 늘 같다(2026-10-16 썰풀다 7DYb inside [323,365] 7.91점으로 1등)
    static = 0.0
    if fr:   # 띠 행만(위아래 여유 행은 영상이라 고정 글자를 묽게 만든다 — 워터마크 '@채널' 띠가 7.49점으로 1등)
        b0, b1 = vl["caption"]["band"]
        r0 = max(0, int((b0 - y0) * CAP_SCALE_H / (y1 - y0)))
        r1 = min(CAP_SCALE_H, max(r0 + 1, int(np.ceil((b1 - y0) * CAP_SCALE_H / (y1 - y0)))))
        sub = [a[r0:r1] for a in fr]
        avg = float(np.mean([a.sum() for a in sub]))
        static = round(float((np.mean(sub, axis=0) >= 0.9).sum()) / avg, 3) if avg > 0 else 0.0
    change = 0.0          # 구간이 하나뿐이면 바뀜을 모른다 = 자막 증거 없음(고정 제목도 구간 하나로 나온다)
    if spans and len(spans) >= 2 and fr:
        mids = [fr[min(len(fr) - 1, int(round((a + b) / 2 * CAP_FPS)))] for a, b in spans]
        ch = [1.0 - (m & n).sum() / max(1, (m | n).sum()) for m, n in zip(mids, mids[1:]) if m.sum() > 30 or n.sum() > 30]
        change = round(float(np.median(ch)), 3) if ch else 0.0
    return {"persist": round(float(np.median(v)), 3) if v else 0.0,
            "coverage": round(float(np.mean([a.sum() > 30 for a in fr])), 3) if fr else 0.0, "change": change, "static": static}


def caption_score(cap: dict, pers: dict) -> float:
    """자막다운 구간 수(길이 CAP_SPAN_OK 안 + 가운데 프레임에 줄 1~3개) × 잉크 지속도 × 잉크 보이는 비율.
    글자 바뀜(change)이 CAP_LINE_CHANGE 미만이면 0 — 영상 내내 같은 글자(고정 제목)는 자막이 아니다.
    (곱하지 않고 문턱으로: 누적형은 1줄→2줄 바뀜이 0.5 안팎이라 곱하면 진짜 자막이 깎인다)"""
    if pers.get("change", 1.0) < CAP_LINE_CHANGE:
        return 0.0
    # 고정 글자 판정은 자막 구간이 CAP_STATIC_MIN_SPANS 이상일 때만 — 자막 2~3개뿐이면 가운데 정렬 글자끼리 획이 겹쳐
    # '늘 찍힌 화소'가 절반을 넘는다(2026-10-16 합성 시험 '스벅 메뉴판에'/'숨겨진 사이즈' 0.57)
    if pers.get("static", 0.0) >= CAP_STATIC_MAX and len(cap.get("spans", [])) >= CAP_STATIC_MIN_SPANS:
        return 0.0
    n = sum(1 for it in cap.get("items", []) if CAP_SPAN_OK[0] <= it["t1"] - it["t0"] <= CAP_SPAN_OK[1]
            and 1 <= it.get("lines", 0) <= 3)
    return round(n * pers["persist"] * pers["coverage"], 2)


def _mid_inks(path: str, vl: dict, cap: dict, y0: int, y1: int, dt: float = 0.0) -> list[np.ndarray]:
    """자막 구간(줄 ≥1)마다 가운데(+dt초) 프레임의 [y0,y1) 잉크 마스크(창 경계 무시)."""
    W = vl["canvas"][0]
    out = []
    for it in cap.get("items", []):
        if it.get("lines", 0) < 1:
            continue
        t = min(it["t1"] - 0.05, (it["t0"] + it["t1"]) / 2 + dt)
        img = probe.grab(path, t, f"crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0)
        if img is not None:
            out.append(ink_mask(img, vl["caption"]["ink"]))
    return out


def _mid_ink_rows(path: str, vl: dict, cap: dict, y0: int, y1: int) -> list[np.ndarray]:
    return [m.sum(axis=1) > GLYPH_ROW_PX for m in _mid_inks(path, vl, cap, y0, y1)]


def tighten_band(path: str, vl: dict, cap: dict) -> list[int] | None:
    """고른 띠를 **실제 글자 행**에 맞춘다(좁히거나 넓힌다): 자막 구간(흔들림 제외)마다 가운데 프레임의 잉크 행(> GLYPH_ROW_PX)을 합친 범위.
    띠 후보는 표본 비율로 잡혀 엔딩·영상이 비친 행까지 넓어진다(2026-10-16 ZdeZRtCeAC4 [1438,1920] → 글자 ≈1466~1529)."""
    if not cap.get("items"):
        return None
    # 띠 높이만큼 위아래로 넓혀 본다(창 경계 자르기는 caption_region 그대로) — 자리를 옮긴 자막이 원래 띠 밖에 있을 수 있다
    # (2026-10-16 썰풀다 w-Yg: 자막이 y≈1320~1400 과 1400~1490 을 오가는데 띠 [1328,1390] 만 봤다)
    b0, b1 = vl["caption"]["band"]
    hgt = b1 - b0
    reg = caption_region({**vl, "caption": {**vl["caption"], "band": [b0 - hgt, b1 + hgt]}})
    if not reg:
        return None
    y0, y1 = reg
    a_ = _mid_inks(path, vl, cap, y0, y1)
    b_ = _mid_inks(path, vl, cap, y0, y1, dt=CAP_EXTEND_DT)
    if not a_ or len(a_) != len(b_):
        return None
    # 구간 안에서 가만히 있는 잉크만(가운데 ∧ +0.2초) — 영상 속 밝은 것은 움직여 빠진다
    rows_l = [((x & y).sum(axis=1) > GLYPH_ROW_PX) for x, y in zip(a_, b_)]
    # 행마다 '그 행에 글자가 있는 자막 구간 비율' f → f ≥ 최댓값×CAP_TIGHT_REL 인 행만 남기고, 틈이 줄 높이의 CAP_TIGHT_GAP 배를
    # 넘으면 끊는다 → f 합이 가장 큰 묶음 = 자막 자리. 모든 프레임을 그냥 합치면 영상 속 밝은 것까지 들어갔다
    # (2026-10-16 썰풀다 7DYb: 자막 행 f 0.67~0.95, 영상 행 ≤0.38 인데 합치면 [929,1156]).
    # 문턱이 최댓값 비례라 자리를 옮겨 다니는 자막(자리마다 f 0.25)도 다 남는다(가만히 있는 잉크로 재면 영상 행은 ≤0.24).
    f = np.mean(rows_l, axis=0)
    keep = f >= CAP_TIGHT_REL * float(f.max()) if f.max() > 0 else f > 0
    runs = segs(keep, min_len=GLYPH_FIRST_LINE_MIN, gap=4)
    if not runs:
        return None
    hs = sorted(e0 - s0 for s0, e0 in runs)
    lh = float(hs[len(hs) // 2])
    groups: list[list[int]] = []
    for s0, e0 in runs:
        if groups and s0 - groups[-1][1] <= CAP_TIGHT_GAP * lh:
            groups[-1][1] = e0
        else:
            groups.append([s0, e0])
    # 원래 띠와 겹치는 묶음 중 글자 비율 합이 가장 큰 것(겹치는 게 없으면 전체에서)
    over = [g for g in groups if g[0] + y0 < b1 and g[1] + y0 > b0] or groups
    g = max(over, key=lambda g: float(f[g[0]:g[1]].sum()))
    return [int(g[0] + y0), int(g[1] + y0)]


def extend_band(path: str, vl: dict, cap: dict) -> list[int] | None:
    """누적형 자막(줄이 덧붙는 꼴)의 다른 줄이 띠 밖(창 경계 너머·머리띠 쪽)에 있을 때 띠를 글자 줄 단위로 넓힌다.
    띠 위아래 CAP_EXTEND_LINES 줄 높이까지 창 경계 무시하고 보고, 띠에 붙은(틈 ≤ 줄 높이) 글자 줄이
    ① 높이가 띠 줄 높이의 0.5~1.6배 ② 아래로 넓힐 줄은 자막 구간 일부에만 있음(덧붙는 줄 — 늘 있으면 영상) ③ 자막 구간끼리 글자가 바뀜(1−IoU 중앙값 ≥ CAP_LINE_CHANGE — 머리띠·제목처럼
    늘 같은 글자면 자막 줄이 아니다) 이면 띠에 넣는다.
    (2026-10-16 방구석 ILIiqCJAOSI: 1줄째 y502~552·3줄째 y660~709 가 띠 [580,676] 밖이라 잘렸고 OCR 이 지어 읽었다)"""
    H = vl["canvas"][1]
    b0, b1 = vl["caption"]["band"]
    fv = {**vl, "caption": {**vl["caption"], "free": True}}
    band_rows = _mid_ink_rows(path, fv, cap, b0, b1)
    lines = [e - s0 for r in band_rows for s0, e in segs(r, min_len=GLYPH_FIRST_LINE_MIN, gap=4)]
    if not lines:
        return None
    lh = float(np.median(lines))
    a0, a1 = max(0, int(b0 - CAP_EXTEND_LINES * lh * 1.4)), min(H, int(b1 + CAP_EXTEND_LINES * lh * 1.4))
    inks = _mid_inks(path, fv, cap, a0, a1)
    inks2 = _mid_inks(path, fv, cap, a0, a1, dt=CAP_EXTEND_DT)
    if len(inks) < 2 or len(inks2) != len(inks):
        return None
    # 줄 후보는 프레임마다 따로 자른 줄을 겹치는 것끼리 묶어 만든다 — 모든 프레임을 합쳐 자르면
    # 틀이 다른 한 장면(훅 카드 큰 글자)이 머리띠·자막 줄을 한 덩어리로 이어 붙였다(2026-10-16 ILIiqCJAOSI).
    per = sorted((s0 + a0, e0 + a0) for m in inks for s0, e0 in segs(m.sum(axis=1) > GLYPH_ROW_PX, min_len=GLYPH_FIRST_LINE_MIN, gap=4)
                 if 0.5 * lh <= e0 - s0 <= 1.6 * lh)
    runs: list[tuple[int, int]] = []
    for s0, e0 in per:
        if runs and s0 < runs[-1][1]:
            runs[-1] = (runs[-1][0], max(runs[-1][1], e0))
        else:
            runs.append((s0, e0))

    def steady(s0, e0):
        """구간 안(가운데 vs +CAP_EXTEND_DT초)에서 그 줄 글자가 그대로인가 — 영상 속 밝은/어두운 것은 움직인다."""
        v = [(x[s0 - a0:e0 - a0] & y[s0 - a0:e0 - a0]).sum() / max(1, (x[s0 - a0:e0 - a0] | y[s0 - a0:e0 - a0]).sum())
             for x, y in zip(inks, inks2) if x[s0 - a0:e0 - a0].any()]
        return float(np.median(v)) if v else 0.0

    def changes(s0, e0):
        ms = [m[s0 - a0:e0 - a0] for m in inks]
        ch = [1.0 - (x & y).sum() / max(1, (x | y).sum()) for x, y in zip(ms, ms[1:]) if x.any() or y.any()]
        return float(np.median(ch)) if ch else 0.0
    lo, hi = b0, b1
    changed = True
    while changed:
        changed = False
        for s0, e0 in runs:
            if s0 >= lo and e0 <= hi:
                continue
            if not (0.5 * lh <= e0 - s0 <= 1.6 * lh) or changes(s0, e0) < CAP_LINE_CHANGE:
                continue
            if steady(s0, e0) < CAP_EXTEND_STEADY:
                continue
            share = sum(1 for m in inks if (m[s0 - a0:e0 - a0].sum(axis=1) > GLYPH_ROW_PX).any()) / len(inks)
            if e0 > hi and -lh <= s0 - hi <= lh and share < CAP_EXTEND_SHARE:   # 아래로 붙은(띠 끝에 걸친) 덧붙는 줄
                hi, changed = e0, True
            elif s0 < lo and -lh <= lo - e0 <= lh:   # 위로 붙은(또는 띠 머리에 걸친) 줄
                lo, changed = s0, True
    if (lo, hi) == (b0, b1):
        return None
    return [int(lo), int(hi)]


def fill_is_bright(path: str, vl: dict, cap: dict) -> float | None:
    """같은 띠에서 bright·dark 두 극성이 비슷한 점수일 때 글자 채움이 밝은지 판정하는 비율.
    = (외곽선에 둘러싸인 밝은 채움 넓이, ink_fill) ÷ (그 채움 8px 안의 어두운 화소 넓이). 흰 글자+검정 외곽선이면 채움이 넓어 ≥ 1 근처,
    흰 바탕 검정 글자면 밝은 채움은 글자 속 구멍뿐이라 작다. (2026-10-16 yummyknow: 구간 수 1개 차이로 극성이 뒤집힘 —
    점수만으로 극성을 정하지 않는다)"""
    reg = caption_region(vl)
    if not reg:
        return None
    y0, y1 = reg
    W = vl["canvas"][0]
    its = [it for it in cap.get("items", []) if it.get("lines", 0) >= 1][:5]
    rs = []
    for it in its:
        img = probe.grab(path, (it["t0"] + it["t1"]) / 2, f"crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0)
        if img is None:
            continue
        fb = ink_fill(img, "bright") & ~ink_mask(img, "dark")
        near = cv2.dilate(fb.astype(np.uint8), np.ones((17, 17), np.uint8)) > 0
        dk = (lum(img) < INK_DARK) & near
        if dk.sum() > 50:
            rs.append(float(fb.sum()) / float(dk.sum()))
    return round(float(np.median(rs)), 3) if rs else None


def choose_caption(path: str, vl: dict, meta: dict, presence: dict, extra: list[dict] | None = None,
                   row_lum=None) -> dict:
    """후보 띠마다 measure_video + persistence → 점수 최고(같으면 좁은 띠) → 글자 행으로 좁히기 → 잘린 줄 넓히기.
    반환 {caption, result, scored, failed?}. 1등 점수가 CAP_MIN_SCORE 미만이면 자막 띠 못 찾음(caption None) —
    점수 0.05 짜리 라벨 띠를 '확인됨'으로 내던 1판 결함(2026-10-16 썰풀다 w-Ygny1f8O8)."""
    scored, best, cands = [], None, []
    for c in band_candidates(vl, presence, extra, row_lum):
        v = {**vl, "caption": c}
        try:
            cap = measure_video(path, v, meta)
        except Exception as e:  # noqa: BLE001 — 후보 하나 실패는 표에 남긴다
            scored.append({**c, "score": None, "failed": f"{type(e).__name__}: {str(e)[:80]}"})
            continue
        pers = persistence(path, v, cap["spans"])
        s = caption_score(cap, pers)
        scored.append({**c, "score": s, "spans": len(cap["spans"]), **pers})
        cands.append((scored[-1], cap))
        h = c["band"][1] - c["band"][0]
        # 점수가 CAP_TIE_FRAC 안으로 비슷하면 넓은 띠 — 장면마다 자리를 옮기는 자막을 다 덮게. 넓은 쪽은 뒤에서 tighten_band 가 글자 행으로 좁힌다
        if best is None or s > best[0] * (1 + CAP_TIE_FRAC) or (s >= best[0] * (1 - CAP_TIE_FRAC) and h > best[3]):
            best = (s, c, cap, h)
    if not best or best[0] < CAP_MIN_SCORE:
        return {"caption": None, "result": None, "scored": scored,
                "failed": f"자막 띠 못 찾음(1등 점수 {best[0] if best else None} < {CAP_MIN_SCORE})"}
    c, cap = best[1], best[2]
    # 극성 다시 보기: 같은 자리(행 50% 이상 겹침) 반대 극성 후보가 점수 CAP_POL_TIE 배 안이면 채움 판정으로 고른다
    rivals = [(x, cp) for x, cp in cands if x["ink"] != c["ink"] and x.get("score") and x["score"] >= CAP_POL_TIE * best[0]
              and min(x["band"][1], c["band"][1]) - max(x["band"][0], c["band"][0]) >= 0.5 * (c["band"][1] - c["band"][0])]
    pol_note = None
    if rivals:
        r = fill_is_bright(path, {**vl, "caption": c}, cap)
        want = "bright" if (r is not None and r >= CAP_FILL_BRIGHT) else "dark"
        pol_note = {"fill_ratio": r, "chose": want, "by": "fill_is_bright"}
        if want != c["ink"]:
            top = max(z[0]["score"] for z in rivals)
            x, cp = max((z for z in rivals if z[0]["score"] >= top * (1 - CAP_TIE_FRAC)),
                        key=lambda z: z[0]["band"][1] - z[0]["band"][0])
            c, cap = {k: x[k] for k in ("pos", "band", "ink") if k in x}, cp
    c = {**c, **({"polarity_check": pol_note} if pol_note else {})}
    tb = tighten_band(path, {**vl, "caption": c}, cap)
    if tb and tb != c["band"]:
        c = {**c, "band": tb, "band_before_tighten": c["band"]}
        cap = measure_video(path, {**vl, "caption": c}, meta)
    eb = extend_band(path, {**vl, "caption": c}, cap)
    if eb:
        c = {**c, "band": eb, "free": True, "band_before_extend": c["band"]}
        cap = measure_video(path, {**vl, "caption": c}, meta)
    return {"caption": c, "result": cap, "scored": scored}


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
