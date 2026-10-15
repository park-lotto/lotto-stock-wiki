# -*- coding: utf-8 -*-
"""bands — L.band_*  창 위 고정 글자 띠(제목·브랜드·광고 표시)의 글자 높이·획 두께·잉크 비율.

띠 좌표는 layout.measure_video 의 `above_bands`(시간평균 그림이 배경과 다른 창 위 행 구간)에서 온다.
글자 모양은 captions.glyph_style 을 그대로 쓴다(자막과 같은 자 — 두 벌 금지). 잉크는 layout.ink_mask 하나.
극성: 창 밖 배경이 밝으면(bg_lum ≥ BG_DARK_LUM) 어두운 글자, 아니면 밝은 글자 — layout 의 판정과 같다.
채널 이름·좌표 없음.

이 모듈의 문턱 BAND_REL·BAND_PAD 는 아래에 둔다(2026-10-16 — constants.py 는 다른 작업이 동시에 고치는 중이라 커밋 섞임을 피함, 옮길 대상).
"""
from __future__ import annotations

import numpy as np

from . import probe
from .layout import ink_mask
from .captions import glyph_style
from .constants import BG_DARK_LUM

BAND_REL = (0.1, 0.25, 0.4, 0.55, 0.7)  # 표본 시각(길이 대비). 0.7 넘으면 엔딩 전체화면이 흔해 뺀다
BAND_PAD = 4                             # 띠 위아래 여유 px(글자 끝이 띠 경계에 걸리는 것 방지)


def polarity(bg_lum: float) -> str:
    return "dark" if bg_lum >= BG_DARK_LUM else "bright"


def band_style(path: str, meta: dict, band: list[int], bg_rgb: list[int], bg_lum: float,
               avoid: list[list[float]] | None = None) -> dict | None:
    """띠 하나: 표본 시각마다 glyph_style(line_h·stroke) + 잉크 비율 → 중앙값. 틀 없는 구간(avoid)의 시각은 건너뛴다."""
    W, H = meta["width"], meta["height"]
    y0, y1 = max(0, band[0] - BAND_PAD), min(H, band[1] + BAND_PAD)
    pol = polarity(bg_lum)
    lh, sw, ink, used = [], [], [], []
    for r in BAND_REL:
        t = r * meta["duration"]
        if avoid and any(a <= t < b for a, b in avoid):
            continue
        img = probe.grab(path, t, f"crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0)
        if img is None:
            continue
        used.append(round(t, 2))
        ink.append(float(ink_mask(img, pol).mean()))
        g = glyph_style(img, pol, bg_rgb)
        if g:
            lh.append(g["line_h"])
            if g.get("stroke"):
                sw.append(g["stroke"])
    if not used:
        return None
    return {"band": [int(band[0]), int(band[1])], "crop": [y0, y1], "ink": pol, "t": used,
            "line_h": float(np.median(lh)) if lh else None, "stroke": float(np.median(sw)) if sw else None,
            "ink_ratio": round(float(np.median(ink)), 5), "method": "bands.band_style(captions.glyph_style+layout.ink_mask)"}


def measure_video(path: str, meta: dict, lv: dict) -> list[dict]:
    """편 하나의 창 위 띠 전부. lv = layout.measure_video 결과(above_bands·bg_rgb·bg_lum)."""
    avoid = (lv.get("frames") or {}).get("other")
    out = []
    for b in lv.get("above_bands") or []:
        s = band_style(path, meta, b, lv["bg_rgb"], lv.get("bg_lum", 255.0), avoid)
        if s:
            out.append(s)
    return out
