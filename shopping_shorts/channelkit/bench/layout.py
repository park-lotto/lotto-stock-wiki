# -*- coding: utf-8 -*-
"""layout — L.*  화면 배치를 영상에서 **자동으로** 찾는다. 다른 모듈은 layout.json만 읽는다.

찾는 것(편마다 → 같은 틀끼리 묶어 채널 값):
  - 영상창(window): 시간에 따라 변하는 화소가 행의 85% 이상인 가장 긴 행 구간 + 그 안의 열 구간
    (편 안에 틀 없는 구간 — 끝 전체화면 엔딩 등 — 이 섞여 창이 화면 전체로 잡히면 시간 조각 다수결 window_vote)
  - 배경색(bg_rgb): 창 밖 시간평균 화소 중앙값
  - 자막띠(caption): 창 **위/아래/안** 중 글자가 자주 바뀌는 곳, 그 행 범위, 잉크 극성(dark/bright)
  - 로고띠(logo): 창 위 글자 행 중 **같은 틀 영상끼리 똑같은** 첫 덩어리(헤드라인은 편마다 다르다)
  - 틀(variant): 창 y 위치·자막 자리가 같은 영상 묶음. 가장 큰 묶음이 채널 대표(main)

채널 이름·좌표 상수는 없다. 문턱은 constants.py에 이름과 이유로만 있다.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np
import cv2

from . import probe
from .constants import (LAYOUT_FPS, LAYOUT_W, WINDOW_PX_STD, WINDOW_ROW_FRAC, WINDOW_COL_FRAC, WINDOW_MIN_PX,
                        SEG_GAP, DYN_ROW_CHG, ROW_CHG_DIFF, INK_ROW_PX, BAND_PRESENCE, LOGO_XVID_STD, LOGO_MIN_H,
                        VARIANT_TOL_PX, BG_DARK_LUM, CAPTION_INSET, INK_DARK, INK_BRIGHT, INK_OUTLINE_DARK,
                        INK_OUTLINE_R, FILL_BG_DIFF, INSIDE_PRESENCE, WINDOW_FULL_FRAC, WINDOW_CHUNK_S,
                        FRAME_SEG_FPS, FRAME_SEG_W, FRAME_SEG_MIN_S,
                        FRAME_BREAK_ABS, FRAME_BREAK_REL, WINDOW_BRIDGE_PX, WINDOW_BRIDGE_FRAC,
                        WINDOW_NONBG_FRAC, WINDOW_SOFT_FRAC, WINDOW_BRIDGE_NONBG, PICTURE_FRAC)


# ── 공용 판정(다른 모듈도 이것을 부른다 — 잉크 정의는 여기 하나) ─────────────────
def lum(img: np.ndarray) -> np.ndarray:
    """RGB → 밝기(BT.601). 잉크·배경 판정의 유일한 밝기 정의."""
    a = img.astype(np.float32)
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def ink_mask(img: np.ndarray, polarity: str) -> np.ndarray:
    """자막 잉크 화소. dark = lum<INK_DARK / bright = lum>INK_BRIGHT 이고 반경 2 안에 외곽선(lum≤60)."""
    L = lum(img)
    if polarity == "dark":
        return L < INK_DARK
    k = 2 * INK_OUTLINE_R + 1
    near_dark = cv2.dilate((L <= INK_OUTLINE_DARK).astype(np.uint8), np.ones((k, k), np.uint8)) > 0
    return (L > INK_BRIGHT) & near_dark


FILL_SPECK_PX = 12       # 채움 마스크에서 버리는 티끌 덩어리(화소)
FILL_LUM_MIN = 110       # 어두운 단색 바탕(제목 띠 등)에서 밝은 글자 채움 문턱 — 노랑(lum≈199)까지 담는다
FILL_BIG_FRAC = 0.15     # 밝은 덩어리가 크롭 넓이의 15% 넘으면 글자가 아니라 배경
FILL_OUTLINED_FRAC = 0.6 # 밝은 덩어리 둘레의 60% 이상이 외곽선 옆이어야 글자 채움


def ink_fill(img: np.ndarray, polarity: str) -> np.ndarray:
    """글자 **채움** 마스크(획 굵기·외곽선·글꼴 대조용). 씨앗 = ink_mask(티끌 제거).
    dark 는 씨앗 그대로. bright 는 ink_mask 정의가 '외곽선 2px 안의 밝은 화소'라 굵은 획은 테두리 고리만 잡힌다
    (2026-10-16 mYxuF1A74j4: 글꼴 점수 0.1 미만·외곽선 판정 실패) → 밝은 덩어리 중 씨앗에 닿고, 크롭의 FILL_BIG_FRAC 보다 작고,
    둘레의 FILL_OUTLINED_FRAC 이상이 어두운 외곽선 옆인 것을 통째로 채운다.
    밝은 문턱: 바탕 중앙 밝기 ≤ INK_OUTLINE_DARK(단색 어두운 띠)면 FILL_LUM_MIN, 아니면 INK_BRIGHT(영상 위 자막 — 낮추면 영상이 붙는다)."""
    seed = ink_mask(img, polarity).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(seed, 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= FILL_SPECK_PX
    seed = keep[lab]
    if polarity != "bright":
        return seed
    L = lum(img)
    thr = FILL_LUM_MIN if float(np.median(L)) <= INK_OUTLINE_DARK else INK_BRIGHT
    bright = (L > thr).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(bright, 8)
    hit = np.zeros(n, bool)
    hit[np.unique(lab[seed])] = True
    hit[0] = False
    hit &= st[:, cv2.CC_STAT_AREA] < FILL_BIG_FRAC * img.shape[0] * img.shape[1]
    k = 2 * INK_OUTLINE_R + 1
    near_dark = cv2.dilate((L <= INK_OUTLINE_DARK).astype(np.uint8), np.ones((k, k), np.uint8)) > 0
    edge = (bright > 0) & ~(cv2.erode(bright, np.ones((3, 3), np.uint8)) > 0)
    tot = np.bincount(lab[edge], minlength=n)
    dark = np.bincount(lab[edge & near_dark], minlength=n)
    hit &= dark >= FILL_OUTLINED_FRAC * np.maximum(tot, 1)
    return hit[lab] | seed


def segs(mask, min_len: int = 1, gap: int = 0) -> list[tuple[int, int]]:
    """참 구간 [(s, e_exclusive)] — gap 이하 틈은 잇는다."""
    idx = np.where(np.asarray(mask))[0]
    if len(idx) == 0:
        return []
    out = []
    s = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev > gap + 1:
            out.append((s, prev + 1))
            s = i
        prev = i
    out.append((s, prev + 1))
    return [x for x in out if x[1] - x[0] >= min_len]


# ── 편 하나 ────────────────────────────────────────────────────────────────
def _scan(path: str, meta: dict, skip: list | None = None) -> dict:
    """LAYOUT_FPS 표본을 한 번 훑어 시간 통계를 모은다(창·배경·자막 판정의 재료).
    skip = [[t0,t1]…] 이면 그 구간 표본은 뺀다(틀이 다른 훅 카드가 흰 여백까지 '움직임'으로 만들어 창이 화면 끝까지 늘었다)."""
    W, H = meta["width"], meta["height"]
    n = 0
    s1 = s2 = srgb = gmin = gmax = None
    rowchg = np.zeros(H)
    ink_rows = {"dark": [], "bright": []}
    prev = None
    for k, f in enumerate(probe.frames(path, f"fps={LAYOUT_FPS},scale={LAYOUT_W}:{H}", LAYOUT_W, H)):
        if skip and any(a <= k / LAYOUT_FPS < b for a, b in skip):
            continue
        g = lum(f).astype(np.float64)
        if s1 is None:
            s1 = np.zeros_like(g); s2 = np.zeros_like(g); srgb = np.zeros(f.shape, np.float64)
            gmin = g.copy(); gmax = g.copy()
        s1 += g; s2 += g * g; srgb += f
        np.minimum(gmin, g, out=gmin); np.maximum(gmax, g, out=gmax)
        if prev is not None:
            rowchg += np.abs(g - prev).mean(axis=1) > ROW_CHG_DIFF
        prev = g
        for pol in ("dark", "bright"):
            ink_rows[pol].append(ink_mask(f, pol).sum(axis=1))
        n += 1
    if n < 3:
        raise ValueError(f"레이아웃 표본 부족({n}): {path}")
    mean = s1 / n
    std = np.sqrt(np.maximum(s2 / n - mean ** 2, 0))
    return {"n": n, "W": W, "H": H, "std": std, "mean_rgb": srgb / n, "rowchg": rowchg / max(1, n - 1),
            "ink_rows": ink_rows, "gmin": gmin, "gmax": gmax}


def _window(st: dict) -> list[int] | None:
    """영상창: 시간 표준편차 > WINDOW_PX_STD 화소가 행의 WINDOW_ROW_FRAC 이상인 가장 긴 행 구간 + 그 안의 열 구간.
    또는 '바탕색과 다른 화소'가 행(열)의 WINDOW_NONBG_FRAC 이상인 행(열) — 덩어리 전체 평균 움직임이 WINDOW_SOFT_FRAC 이상일 때만 창.
    카메라가 고정된 영상(벽 앞 인물 등)은 움직이는 화소가 행의 85%가 안 돼 창이 없었다(2026-10-16 핫템 1·2위 창 None).
    바탕색 = 가만히 있는 화소의 시간평균 색 중 가장 흔한 색(32단계 양자화 최빈) — 틀 바탕은 넓고 고르다."""
    sx = st["W"] / LAYOUT_W
    hot = st["std"] > WINDOW_PX_STD
    q = (st["mean_rgb"] // 8).astype(np.int32)
    key = q[..., 0] * 1024 + q[..., 1] * 32 + q[..., 2]
    # 최빈색은 가만히 있는 화소에서만 센다 — 움직이는 영상의 시간평균이 고른 회색이 되어 바탕으로 뽑히지 않게
    still_key = key[~hot] if (~hot).sum() > 100 else key.ravel()
    vals, cnt = np.unique(still_key, return_counts=True)
    m = int(vals[np.argmax(cnt)])
    bg = np.array([m // 1024, (m // 32) % 32, m % 32], np.float64) * 8 + 4
    nonbg = np.abs(st["mean_rgb"] - bg[None, None, :]).max(axis=2) > FILL_BG_DIFF
    rf = hot.mean(axis=1)
    row_ok = (rf > WINDOW_ROW_FRAC) | (nonbg.mean(axis=1) > WINDOW_NONBG_FRAC)
    runs = segs(row_ok, gap=SEG_GAP)
    # 창 안에 오래 가만히 있는 넓은 자막 줄이 있으면 그 행만 '덜 움직여' 창이 둘로 갈린다 → 위아래 창 조각 사이 틈이
    # WINDOW_BRIDGE_PX 이하이고 틈 행이 바탕색 아닌 화소 WINDOW_BRIDGE_NONBG 이상이면 잇는다(창 안 넓은 자막 줄·영상 속 정지 행)
    merged: list[list[int]] = []
    for a_, b_ in runs:
        gap_ok = merged and a_ - merged[-1][1] <= WINDOW_BRIDGE_PX * st["H"]   # 움직임 조건은 뺐다: 영상 속 정지 행(지붕·하늘)도 창(핫템 vLcK)
        # 틈 행이 바탕색이면(흰 틀 위 자막 줄 — 방구석 ILIiqCJAOSI 창이 582로 올라감) 창 안이 아니다 → 잇지 않는다
        if gap_ok and nonbg[merged[-1][1]:a_].mean() >= WINDOW_BRIDGE_NONBG:
            merged[-1][1] = b_
        else:
            merged.append([a_, b_])
    # 바탕과 다른 덩어리라도 거의 안 움직이면(고정 제목 상자·검정 띠) 창이 아니다 — 덩어리 평균 움직임 ≥ WINDOW_SOFT_FRAC
    rows = [(a_, b_) for a_, b_ in merged if b_ - a_ >= WINDOW_MIN_PX and rf[a_:b_].mean() >= WINDOW_SOFT_FRAC]
    if not rows:
        return None
    y0, y1 = max(rows, key=lambda s: s[1] - s[0])
    cf = hot[y0:y1].mean(axis=0)
    col_ok = (cf > WINDOW_COL_FRAC) | (nonbg[y0:y1].mean(axis=0) > WINDOW_NONBG_FRAC)
    cols = segs(col_ok, min_len=int(WINDOW_MIN_PX / sx), gap=SEG_GAP)
    c0, c1 = max(cols, key=lambda s: s[1] - s[0]) if cols else (0, LAYOUT_W)
    x0 = int(round(c0 * sx)); x1 = int(round(c1 * sx))
    return [x0, int(y0), x1 - x0, int(y1 - y0)]


def picture_box(img: np.ndarray, bg_rgb: list[int], win: list[int] | None = None) -> list[int] | None:
    """프레임 한 장의 그림 칸 [x,y,w,h](그 프레임 좌표) — 틀 바탕색과 다른 화소가 행·열의 PICTURE_FRAC 이상인 가장 긴 덩어리.
    창(편 전체 시간 통계)은 컷마다 크기가 다른 그림 칸을 한 값으로 뭉갠다(2026-10-16 방구석: 전폭 ↔ x19~1057) → 컷 가운데 프레임마다 잰다.
    win(같은 좌표계)이 있으면 그 행 범위 ±10% 안에서만 찾는다(제목·자막 띠 제외)."""
    a = img.astype(np.int16)
    nonbg = np.abs(a - np.array(bg_rgb, np.int16)[None, None, :]).max(axis=2) > FILL_BG_DIFF
    H, W = nonbg.shape
    r0, r1 = 0, H
    if win:
        pad = int(0.1 * win[3])
        r0, r1 = max(0, win[1] - pad), min(H, win[1] + win[3] + pad)
    rows = segs(nonbg[r0:r1].mean(axis=1) > PICTURE_FRAC, min_len=max(4, H // 20), gap=max(2, H // 200))
    if not rows:
        return None
    y0, y1 = max(rows, key=lambda r: r[1] - r[0])
    y0, y1 = y0 + r0, y1 + r0
    cols = segs(nonbg[y0:y1].mean(axis=0) > PICTURE_FRAC, min_len=max(4, W // 20), gap=max(2, W // 200))
    if not cols:
        return None
    x0, x1 = max(cols, key=lambda c: c[1] - c[0])
    return [int(x0), int(y0), int(x1 - x0), int(y1 - y0)]


def _finish(win, st: dict) -> dict:
    """창이 정해진 뒤의 배경·극성·정지 글자 띠·자막 자리(편 전체 통계로)."""
    H, n, mean_rgb = st["H"], st["n"], st["mean_rgb"]
    outside = np.ones(H, bool)
    if win:
        outside[win[1]:win[1] + win[3]] = False
    bg = np.median(mean_rgb[outside].reshape(-1, 3), axis=0) if outside.any() else np.median(mean_rgb.reshape(-1, 3), axis=0)
    bg_rgb = [int(round(v)) for v in bg]
    bg_lum = float(0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2])
    outside_pol = "dark" if bg_lum >= BG_DARK_LUM else "bright"

    # 정지 글자 띠(창 위/아래): 시간평균 그림이 배경과 다른 행
    diff_bg = np.abs(mean_rgb - bg[None, None, :]).max(axis=2) > FILL_BG_DIFF
    static_rows = diff_bg.mean(axis=1) > 0.004
    above_bands = [list(s) for s in segs(static_rows[:win[1]], min_len=6)] if win else []

    caption = _caption(win, H, st["rowchg"], st["ink_rows"], outside_pol, n)
    return {
        "window": win, "bg_rgb": bg_rgb, "bg_lum": round(bg_lum, 1), "caption": caption,
        "above_bands": above_bands, "n_samples": n,
        # 로고 판정용: 글자가 한 번이라도 찍힌 모습(밝은 배경 → 시간 최솟값, 어두운 배경 → 최댓값).
        # 로고가 편마다 보이는 시간이 달라 시간평균은 편끼리 안 맞는다(2026-09-28 실측 최솟값 0~228).
        "_above_ext": (st["gmin"] if outside_pol == "dark" else st["gmax"])[:win[1]].astype(np.float32) if win else None,
        # 편 하나 자막 띠 후보(captions.choose_caption)용: 극성별 '행에 잉크 있음' 표본 비율
        "_presence": {p: (np.array(r) > INK_ROW_PX).mean(axis=0) for p, r in st["ink_rows"].items()},
        # 행별 시간평균 밝기 중앙값 — 자막 띠 극성 거르기(captions.band_candidates)
        "_row_lum": np.median(lum(mean_rgb), axis=1).astype(np.float32),
    }


def _same_window(a, b) -> bool:
    return bool(a and b and abs(a[1] - b[1]) <= VARIANT_TOL_PX and abs((a[1] + a[3]) - (b[1] + b[3])) <= VARIANT_TOL_PX)


def window_vote(path: str, meta: dict) -> dict | None:
    """편을 WINDOW_CHUNK_S 조각으로 잘라 조각마다 _window → 같은 창(VARIANT_TOL_PX)끼리 묶어 다수결.
    반환 {window(중앙값), chunks:[{t,window}], main:[[t0,t1]…], other:[[t0,t1]…], votes} — 다수가 없으면 None."""
    H, d = meta["height"], meta["duration"]
    n = max(3, int(round(d / WINDOW_CHUNK_S)))
    chunks = []
    with tempfile.TemporaryDirectory() as td:
        for i in range(n):
            a, b = d * i / n, d * (i + 1) / n
            p = os.path.join(td, f"c{i}.mp4")
            probe.clip(path, a, b, p)
            try:
                w = _window(_scan(p, probe.info(p)))
            except ValueError as e:      # 표본 부족 조각은 표에 남기고 다수결에서 뺀다
                chunks.append({"t": [round(a, 2), round(b, 2)], "window": None, "failed": str(e)[:80]})
                continue
            chunks.append({"t": [round(a, 2), round(b, 2)], "window": w})
    groups: list[list[dict]] = []
    for c in chunks:
        if not c["window"] or c["window"][3] >= WINDOW_FULL_FRAC * H:
            continue
        for g in groups:
            if _same_window(g[0]["window"], c["window"]):
                g.append(c)
                break
        else:
            groups.append([c])
    if not groups:
        return None
    g = max(groups, key=len)
    if len(g) * 2 <= n:     # 과반 미달 = 틀 없는 전체화면 편 — 창을 지어내지 않는다(2026-10-16 썰풀다 D3Pc6HZ6t6c 1/3로 창을 지어냄)
        return None
    win = [int(np.median([c["window"][k] for c in g])) for k in range(4)]
    main = [c["t"] for c in g]
    other_chunks = [c["t"] for c in chunks if c not in g]
    seg = frame_segments(path, meta, win, main, other_chunks)
    return {"window": win, "chunks": chunks, "main": main, "other_chunks": other_chunks,
            "other": seg["other"], "other_method": seg["method"], "votes": f"{len(g)}/{n}"}


def frame_segments(path: str, meta: dict, win: list[int], main: list[list[float]], other: list[list[float]]) -> dict:
    """조각 다수결로 찾은 '틀 없는 구간'의 경계를 프레임 단위(FRAME_SEG_FPS)로 좁힌다.
    프레임마다 창 밖(틀 자리) 회색이 '틀 있는 조각들의 중앙값 그림'과 얼마나 다른지 d(t) → 문턱 = 틀 구간 d 중앙값과
    틀 없는 조각 d p90 의 가운데. 문턱 넘는 프레임이 FRAME_SEG_MIN_S 이상 이어진 곳 = 틀 없는 구간.
    (2026-10-16 ZdeZRtCeAC4: 조각 경계 17.92초 → 실측 21.7초, 틀 구간 d≈3 / 엔딩 d≈120)"""
    H = meta["height"]
    sh = int(round(H * FRAME_SEG_W / meta["width"] / 2) * 2)
    fr = np.array([f.astype(np.float32) for f in probe.frames(path, f"fps={FRAME_SEG_FPS},scale={FRAME_SEG_W}:{sh}",
                                                               FRAME_SEG_W, sh, "gray")])
    if len(fr) < 3 or not other:
        return {"other": other, "method": "조각 단위(프레임 표본 부족)"}
    rows = np.ones(sh, bool)
    k = sh / H
    rows[int(win[1] * k):int(np.ceil((win[1] + win[3]) * k))] = False
    if not rows.any():
        return {"other": other, "method": "조각 단위(창 밖 행 없음)"}
    t = np.arange(len(fr)) / FRAME_SEG_FPS

    def inside(spans):
        return np.array([any(a <= x < b for a, b in spans) for x in t])
    m_main, m_other = inside(main), inside(other)
    if not m_main.any() or not m_other.any():
        return {"other": other, "method": "조각 단위(표본 없음)"}
    tpl = np.median(fr[m_main][:, rows], axis=0)
    d = np.abs(fr[:, rows] - tpl).mean(axis=(1, 2))
    lo, hi = float(np.median(d[m_main])), float(np.percentile(d[m_other], 90))   # 틀 없는 조각엔 틀 있는 앞부분이 섞여 있어 p90
    if hi - lo < 10:
        return {"other": other, "method": f"조각 단위(틀 차이 작음 {lo:.1f}/{hi:.1f})"}
    thr = (lo + hi) / 2
    runs = segs(d > thr, min_len=max(1, int(round(FRAME_SEG_MIN_S * FRAME_SEG_FPS))), gap=1)
    out = [[round(a / FRAME_SEG_FPS, 2), round(min(len(fr), b) / FRAME_SEG_FPS, 2)] for a, b in runs]
    return {"other": out or other,
            "method": f"창 밖 회색 차 d(t) {FRAME_SEG_FPS}fps > {thr:.1f}(틀 {lo:.1f}·틀 없음 {hi:.1f}의 가운데)"}


def frame_breaks(path: str, meta: dict, win: list[int]) -> dict:
    """창이 정상으로 잡힌 편에서도 틀이 잠깐 다른 구간(훅 카드·인트로·엔딩)을 프레임 단위로 찾는다.
    d(t) = 창 밖(틀 자리) 회색이 편 전체 중앙값 그림과 다른 정도. 문턱 = max(FRAME_BREAK_ABS, FRAME_BREAK_REL × 중앙값 d).
    (2026-10-16 방구석 ILIiqCJAOSI 0~1.63초 훅 카드 · 핫템 0~3초 분홍 인트로를 '없음'으로 냈다)"""
    H = meta["height"]
    sh = int(round(H * FRAME_SEG_W / meta["width"] / 2) * 2)
    fr = np.array([f.astype(np.float32) for f in probe.frames(path, f"fps={FRAME_SEG_FPS},scale={FRAME_SEG_W}:{sh}",
                                                               FRAME_SEG_W, sh, "gray")])
    if len(fr) < 3:
        return {"other": [], "method": "프레임 표본 부족"}
    rows = np.ones(sh, bool)
    k = sh / H
    rows[int(win[1] * k):int(np.ceil((win[1] + win[3]) * k))] = False
    if rows.sum() < 3:
        return {"other": [], "method": "창 밖 행 없음"}
    tpl = np.median(fr[:, rows], axis=0)
    d = np.abs(fr[:, rows] - tpl).mean(axis=(1, 2))
    thr = max(FRAME_BREAK_ABS, FRAME_BREAK_REL * float(np.median(d)))
    runs = segs(d > thr, min_len=max(1, int(round(FRAME_SEG_MIN_S * FRAME_SEG_FPS))), gap=1)
    out = [[round(a / FRAME_SEG_FPS, 2), round(min(len(fr), b) / FRAME_SEG_FPS, 2)] for a, b in runs]
    return {"other": out, "method": f"창 밖 회색 차 d(t) {FRAME_SEG_FPS}fps > {thr:.1f}(편 중앙값 {float(np.median(d)):.1f})"}


def measure_video(path: str, meta: dict) -> dict:
    """편 하나의 배치. `_above_ext`·`_presence`는 내부 자료다(json에 안 쓴다).
    편 전체로 잰 창이 없거나 화면 거의 전체(WINDOW_FULL_FRAC)면 — 틀 없는 구간(전체화면 엔딩 등)이 섞인 것 —
    시간 조각 다수결(window_vote)로 창을 다시 잡고, 배경·자막 자리는 편 전체 통계를 그 창으로 다시 잰다."""
    st = _scan(path, meta)
    win = _window(st)
    method, frames = "layout._window(편 전체)", None
    if win is None or win[3] >= WINDOW_FULL_FRAC * st["H"]:
        v = window_vote(path, meta)
        if v:
            win, method = v["window"], f"layout.window_vote(조각 다수결 {v['votes']})"
            frames = {"main": v["main"], "other": v["other"], "other_chunks": v["other_chunks"],
                      "other_method": v["other_method"], "chunks": v["chunks"]}
        elif win is not None:
            method = "layout._window(편 전체) — 조각 다수결 미달: 틀 없는 전체화면 편"
    if frames is None and win is not None and win[3] < WINDOW_FULL_FRAC * st["H"]:
        fb = frame_breaks(path, meta, win)       # 짧은 다른 틀(첫 1~3초 훅 카드·인트로)은 6초 조각 다수결로 안 보인다
        if fb["other"]:
            frames = {"main": None, "other": fb["other"], "other_method": fb["method"], "chunks": []}
            # 그 구간을 빼고 창·통계를 다시 잰다(방구석 ayNy6CSSrIQ: 훅 카드가 아래 흰 여백을 덮어 창 아래 끝이 1920)
            try:
                st2 = _scan(path, meta, skip=fb["other"])
                w2 = _window(st2)
            except ValueError:
                w2 = None
            if w2 and w2[3] < WINDOW_FULL_FRAC * st["H"]:
                if w2 != win:
                    frames["window_before_skip"] = win
                    method += " — 틀 다른 구간 빼고 다시"
                st, win = st2, w2
    lv = _finish(win, st)
    lv["window_method"] = method
    if frames:
        lv["frame_segments"] = frames
    return lv


def _caption(win, H, rowchg, ink_rows, outside_pol, n) -> dict:
    """자막 자리: 창 밖(위/아래)에서 자주 바뀌는 글자 행이 있으면 그쪽, 없으면 창 안 밝은 외곽선 글자."""
    if not win:
        return {"pos": "none", "band": None, "ink": None}
    wy0, wy1 = win[1], win[1] + win[3]
    pres = {p: (np.array(r) > INK_ROW_PX).mean(axis=0) for p, r in ink_rows.items()}
    regions = {"above": (0, max(0, wy0 - CAPTION_INSET)), "below": (min(H, wy1 + CAPTION_INSET), H)}
    best = None
    for pos, (a, b) in regions.items():
        if b - a < 10:
            continue
        dyn = rowchg[a:b] > DYN_ROW_CHG
        if dyn.sum() < 10:
            continue
        if best is None or dyn.sum() > best[1]:
            best = (pos, int(dyn.sum()), a, b)
    if best:
        pos, _, a, b = best
        dyn_rows = set(np.where(rowchg[a:b] > DYN_ROW_CHG)[0] + a)
        runs = [(s + a, e + a) for s, e in segs(pres[outside_pol][a:b] >= BAND_PRESENCE, min_len=4, gap=SEG_GAP * 4)]
        runs = [r for r in runs if any(y in dyn_rows for y in range(r[0], r[1]))]
        if runs:
            return {"pos": pos, "band": [int(min(r[0] for r in runs)), int(max(r[1] for r in runs))], "ink": outside_pol}
    # 창 안(하드섭): 밝은 글자 + 외곽선이 표본의 INSIDE_PRESENCE 이상에서 보이는 행
    inside = pres["bright"][wy0:wy1]
    runs = segs(inside >= INSIDE_PRESENCE, min_len=10, gap=SEG_GAP * 4)
    if runs:
        s, e = max(runs, key=lambda r: inside[r[0]:r[1]].sum())
        return {"pos": "inside", "band": [int(s + wy0), int(e + wy0)], "ink": "bright"}
    return {"pos": "none", "band": None, "ink": None}


# ── 채널(틀 묶음) ──────────────────────────────────────────────────────────
def _same_variant(a: dict, b: dict) -> bool:
    wa, wb = a["window"], b["window"]
    if not wa or not wb:
        return wa == wb
    return (abs(wa[1] - wb[1]) <= VARIANT_TOL_PX and abs((wa[1] + wa[3]) - (wb[1] + wb[3])) <= VARIANT_TOL_PX
            and a["caption"]["pos"] == b["caption"]["pos"])


def _logo(members: list[dict]) -> list[int] | None:
    """같은 틀 영상들의 창 위 '글자 찍힌 모습'을 겹쳐, 편끼리 똑같은 글자 행의 첫 덩어리 = 로고."""
    imgs = [m["_above_ext"] for m in members if m.get("_above_ext") is not None]
    if len(imgs) < 2:
        return None
    h = min(i.shape[0] for i in imgs)
    st = np.stack([i[:h] for i in imgs])
    med = np.median(st, axis=0)
    bgl = float(np.median(med))
    ink = np.abs(med - bgl) > FILL_BG_DIFF
    xstd = st.std(axis=0)
    rows = []
    for y in range(h):
        m = ink[y]
        rows.append(m.mean() > 0.004 and float(xstd[y][m].mean()) < LOGO_XVID_STD)
    runs = segs(np.array(rows), min_len=LOGO_MIN_H, gap=SEG_GAP)
    return [int(runs[0][0]), int(runs[0][1])] if runs else None


def consolidate(per_video: dict[str, dict], canvas: list[int]) -> dict:
    """편별 배치 → 틀 묶음 → 채널 layout.json 내용."""
    groups: list[list[str]] = []
    for vid, lv in per_video.items():
        for g in groups:
            if _same_variant(per_video[g[0]], lv):
                g.append(vid)
                break
        else:
            groups.append([vid])
    groups.sort(key=len, reverse=True)
    variants = []
    for i, g in enumerate(groups):
        ms = [per_video[v] for v in g]
        wins = [m["window"] for m in ms if m["window"]]
        win = [int(np.median([w[k] for w in wins])) for k in range(4)] if wins else None
        bands = [m["caption"]["band"] for m in ms if m["caption"]["band"]]
        cap = {"pos": ms[0]["caption"]["pos"], "ink": ms[0]["caption"]["ink"],
               "band": [int(min(b[0] for b in bands)), int(max(b[1] for b in bands))] if bands else None}
        variants.append({
            "id": chr(ord("A") + i), "videos": g, "window": win,
            "window_y_per_video": {v: [per_video[v]["window"][1], per_video[v]["window"][1] + per_video[v]["window"][3]]
                                   for v in g if per_video[v]["window"]},
            "caption": cap, "logo": _logo(ms),
            "bg_rgb": [int(np.median([m["bg_rgb"][k] for m in ms])) for k in range(3)],
        })
    main = variants[0]
    return {
        "canvas": canvas, "main": main["id"], "variants": variants,
        "per_video": {v: {k: val for k, val in lv.items() if not k.startswith("_")} for v, lv in per_video.items()},
    }


def variant_of(layout: dict, vid: str) -> dict:
    """그 편이 속한 틀."""
    for v in layout["variants"]:
        if vid in v["videos"]:
            return v
    raise KeyError(vid)


def video_layout(layout: dict, vid: str) -> dict:
    """자 모듈이 쓰는 편 하나의 좌표: 창·자막띠는 **그 편** 값, 극성·자리는 틀 값."""
    pv = layout["per_video"][vid]
    var = variant_of(layout, vid)
    cap = dict(pv["caption"])
    if cap.get("band") is None and var["caption"]["band"]:
        cap = dict(var["caption"])
    return {"window": pv["window"], "caption": cap, "bg_rgb": pv["bg_rgb"], "variant": var["id"],
            "canvas": layout["canvas"]}
