# -*- coding: utf-8 -*-
"""뜯기(2판) → 틀 여러 장 설명서(frames + 시간축) — 게시글형(헤더 띠·프로필 줄·좌정렬 글 제목·구분선·누적 자막·가변 그림 칸) 같은 틀.

    PYTHONUTF8=1 py tools/calcopy/engine/to_frame_multi.py <뜯기.json> --out frame.json [--ocr-from hook=<frame.json> body=<frame.json>]

언제 쓰나: 뜯기 layout.other_frame_segments 에 **끝이 아닌** 구간(예: 훅 카드 0~1.5초)이 있을 때. to_frame.py(틀 한 장 + 꼬리 끄기)로는
표현이 안 된다(yummyknow rGFXQlS9Cp4: to_frame 이 띠 5개를 제목 5줄로 읽어 실패, 2026-10-16).
판단 주인: 틀 나누기·층 분류는 build_multi() 한 곳. 재기는 원본 프레임 한 장씩(구간 가운데) — 층 분류 규칙:
  띠(band)     = 행의 주된 색이 바탕과 다르고 가로 85% 이상을 덮는 행 묶음(헤더 띠·회색 띠)
  구분선       = 어두운 화소가 가로 90% 이상인 높이 4px 이하 행
  상자(band)   = 행 묶음 안에서 바탕과 다른 단색 덩어리(가로·세로 50~260px, 프로필 아이콘 칸)
  글자(text)   = 바탕(또는 띠)과 80 넘게 다른 화소의 행 묶음 → 가로 60px 넘게 떨어지면 따로(헤더의 » · 채널명 · 🍽)
  자막(caption)= 뜯기 captions(top_y·leading·줄 수) — 누적형이면 valign top(1줄일 때도 첫 줄 자리)
  영상 창      = 뜯기 cuts.picture_boxes 컷별 [x,y,w,h] → video.cuts(가변 그림 칸), 본문은 anchor below caption(gap = 컷들의 중앙값)
글자 내용은 OCR 이 필요하다 — 무료 제미나이가 막혔을 때는 --ocr-from 으로 예전(손) 설명서의 같은 틀 글을 y 가 가까운 것끼리 이어 쓴다.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import schema  # noqa: E402
from tools.calcopy.engine import to_frame as T  # noqa: E402

DIFF = 40            # 바탕과 다르다
INK = 80             # 글자(띠·바탕과 이만큼 다른 점)
EDGE = 20            # 띠 판정에 보는 화면 양 끝 폭(px)
SPLIT_GAP = 45       # 같은 행 묶음 안 글자 덩어리를 가르는 가로 틈(px)
FONT_MIN = 0.6       # 글꼴 판별 1위 점수가 이보다 낮으면 기본(자막) 글꼴
NL = chr(10)
OCR_MATCH_PX = 45    # 예전 설명서 글을 이을 때 y 중심 허용 차


def _mode_color(px: np.ndarray) -> tuple[list, float]:
    q = (px // 8).astype(np.int32)
    key = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    vals, cnt = np.unique(key, return_counts=True)
    k = vals[cnt.argmax()]
    sel = key == k
    return [int(v) for v in np.median(px[sel], axis=0)], float(cnt.max() / len(key))


def _runs(mask: np.ndarray, min_len: int = 1, gap: int = 0) -> list[tuple[int, int]]:
    """참인 칸의 [시작, 끝] 묶음(끝 포함). gap 이하 빈칸은 이어 붙인다."""
    idx = np.where(mask)[0]
    out = []
    for i in idx:
        if out and i - out[-1][1] <= gap + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return [(int(a), int(b)) for a, b in out if b - a + 1 >= min_len]


STILL_DIFF = 8.0     # 같은 구간 다른 시각 두 장의 평균 차가 이보다 크면 움직이는 줄(영상) — 틀(띠)은 가만히 있다



LOW_DIFF = 6         # 바탕과 조금만 다른 띠(어두운 머리 띠) — 양 끝 색이 바탕과 이만큼 넘게 다르면
LOW_MIN_H = 20       # 그런 행이 이만큼 이어져야 띠(그라데이션 띠 가장자리 번짐 10줄 안팎은 띠가 아니다)
INK_DARK_BAND = 35   # 어두운 띠 안 글자·선 그림 문턱
FADE_MIN_FRAC = 0.15  # 바탕 쪽으로 이만큼 넘게 띠 색이 남은 줄만 번짐으로 센다
FADE_MIN_ROWS = 6    # 번짐 줄이 이만큼 안 되면 번짐이 아니라 가장자리 압축 번짐
FADE_FULL = 0.85     # 번진 가장자리: 띠 밝기(바탕→띠)가 이 비율에 닿는 줄부터 온전한 띠
GRAD_MIN = 25        # 띠 가로 색 변화가 이보다 크면 grad_x 로 칠한다
GRAD_POS = (0, 0.03, 0.08, 0.15, 0.3, 0.5, 0.7, 0.85, 0.92, 0.97, 1)


def _band_paint(a, b, bg, keep, W):
    """띠 하나의 칠 — 위·아래로 바탕에 번진 줄(fade)과 가로 색 변화(grad_x). 글자 없는 줄(가로 거칠기 작은 줄)로 잰다.
    훅 회색 띠(rGFX): 바탕 64 → 556줄부터 밝아져 585줄에 띠 밝기(가운데 242·양 끝 156/170), 띠 높이 위쪽 30줄이 번짐."""
    H = a.shape[0]
    bgl = float(np.mean(bg))
    core = [y for y in range(b["y"], b["y"] + b["h"])]
    # 번짐 비율 = 1 − (그 줄 양 끝 색과 띠 양 끝 색의 거리) / (바탕과 띠 양 끝 색의 거리). 양 끝만 본다 — 가운데는 글자가 얹히고,
    #   훅 회색 띠처럼 가운데만 늦게 밝아지는 띠도 끝은 띠 색이다. 채널 최대 차로 잰다(압축으로 한 채널이 2~4 흔들려도 띠다).
    edge = {y: np.median(np.concatenate([a[y, :EDGE], a[y, W - EDGE:]]), axis=0) for y in range(H)}
    band_e = np.median(np.array([edge[y] for y in core]), axis=0)
    span = max(1.0, float(np.abs(band_e - np.array(bg)).max()))

    # 가운데도 같이 본다 — 훅 회색 띠는 끝이 574줄에 띠 색인데 가운데는 585줄에야 닿는다(둥글게 번진 띠). 번짐 비율 = 끝·가운데 평균.
    cx = W // 2
    cen = {y: float(np.median(a[y, cx - EDGE:cx + EDGE])) for y in range(H)}
    # 가운데에 글자가 얹힌 줄(가운데 조각이 고르지 않은 줄)은 가운데를 안 본다 — 본문 머리 띠 '친구들' 줄을 번짐으로 읽었다
    smooth = {y: float(np.std(a[y, cx - EDGE:cx + EDGE])) < 8 for y in range(H)}
    cen_core = [cen[y] for y in core if smooth[y]] or [float(np.mean(band_e))]
    band_c = float(np.percentile(cen_core, 90 if float(np.mean(band_e)) > bgl else 10))   # 글자 줄은 가운데가 글자 색이라 띠 쪽 끝값
    span_c = max(1.0, abs(band_c - bgl))

    def frac(y):
        fe = 1 - float(np.abs(edge[y] - band_e).max()) / span
        if not smooth[y]:
            return fe
        fc = 1 - min(1.0, abs(cen[y] - band_c) / span_c)
        return (fe + fc) / 2
    lv_m = {y: float(np.median(a[y])) for y in range(H)}
    lv_core = [lv_m[y] for y in core]
    full_m = max(lv_core) if float(np.mean(band_e)) > bgl else min(lv_core)   # 띠 쪽 끝 밝기(글자 줄은 가운데값이 글자 쪽으로 끌린다)
    top = b["y"]
    while top - 1 >= 0 and keep[top - 1] and FADE_MIN_FRAC < frac(top - 1) < 1 and np.std(a[top - 1]) < 30:
        top -= 1
    bot = b["y"] + b["h"] - 1
    while bot + 1 < H and keep[bot + 1] and FADE_MIN_FRAC < frac(bot + 1) < 1 and np.std(a[bot + 1]) < 30:
        bot += 1
    # 몇 줄짜리 가장자리(압축 번짐 — 본문 머리 띠 아래 234~236줄)는 번짐이 아니다: 늘리지 않는다(늘리니 흰 바탕에 연두 줄이 생겼다)
    #   번짐 줄 수 = 늘린 줄 중 띠 밝기에 못 미친 줄(FADE_FULL 아래) — 띠 색 그대로인 줄(본문 234~236)은 번짐이 아니라 띠다
    #   번짐 줄 수 = 바깥 끝(top/bot)부터 띠 밝기(FADE_FULL)에 닿는 줄까지 — 띠 안쪽 번짐 줄도 센다(훅 회색 띠는 띠로 잡힌 566줄 위아래로 번진다)
    f_top = next((y for y in range(top, bot + 1) if frac(y) >= FADE_FULL), top)
    f_bot = next((y for y in range(bot, top - 1, -1) if frac(y) >= FADE_FULL), bot)
    if f_top - top < FADE_MIN_ROWS:
        top = f_top
    if bot - f_bot < FADE_MIN_ROWS:
        bot = f_bot
    b["y"], b["h"] = top, bot - top + 1          # 늘린 띠 색 줄도 띠(번짐이 없어도 — 본문 머리 띠 234~235줄이 빠졌던 것)
    if f_top - top or bot - f_bot:
        b["fade"] = [f_top - top, bot - f_bot]
    near = lambda y: abs(lv_m[y] - full_m) <= 0.05 * abs(full_m - bgl) + 1   # noqa: E731 — 띠 밝기에 닿은 줄만(가장자리 번짐 줄 빼고)
    rough = [y for y in range(f_top, f_bot + 1) if near(y) and float(np.abs(np.diff(a[y], axis=0)).mean()) < 1.5]
    if not rough:
        return
    prof = np.median(a[rough], axis=0)                                    # 칸마다 띠 색(W,3)
    k = 15
    pad = np.pad(prof, ((k, k), (0, 0)), mode="edge")
    prof = np.array([np.median(pad[x:x + 2 * k + 1], axis=0) for x in range(W)])
    b["rgb"] = [int(v) for v in prof[W // 2]]
    if float(np.ptp(prof.mean(axis=1))) > GRAD_MIN:
        b["grad_x"] = [[p, [int(v) for v in prof[min(W - 1, int(round(p * (W - 1))))]]] for p in GRAD_POS]
        b["_profile"] = prof.astype(int)

def analyze_image(img: np.ndarray, skip_rows: list[tuple[int, int]], video_rect, img2: np.ndarray | None = None) -> dict:
    """원본 프레임 한 장 → 바탕·띠·구분선·상자·글자 덩어리. skip_rows(자막 칸 등)와 영상 창은 건너뛴다."""
    H, W = img.shape[:2]
    a = img.astype(int)
    keep = np.ones(H, bool)
    for y0, y1 in skip_rows:
        keep[max(0, y0):min(H, y1 + 1)] = False
    vx, vy, vw, vh = video_rect if video_rect else (0, H, 0, 0)
    keep[max(0, vy):min(H, vy + vh)] = False
    ext = []
    if video_rect and img2 is not None:
        # 영상 창에 붙어 이어지는 '움직이는 줄'(같은 구간 다른 시각과 평균 차 > STILL_DIFF) = 영상이 뜯기 그림 칸보다 더 나온 것
        mv = np.abs(a - img2.astype(int)).mean(axis=(1, 2)) > STILL_DIFF
        y = vy + vh
        while y < H and mv[y]:
            y += 1
        if y > vy + vh + 2:
            ext.append((vy + vh, y - 1))
        y = vy - 1
        while y >= 0 and mv[y]:
            y -= 1
        if y < vy - 3:
            ext.append((y + 1, vy - 1))
        for y0, y1 in ext:
            keep[y0:y1 + 1] = False
    outside = a[keep]
    bg, _ = _mode_color(outside.reshape(-1, 3))
    diff = np.abs(a - np.array(bg)).max(axis=2) > DIFF
    bands, dividers, boxes, texts = [], [], [], []
    # 띠 행 · 구분선 행 — 띠는 화면 양 끝(좌우 EDGE px)이 바탕과 다른 같은 색인 행. 가운데에 글자가 얹혀도(헤더 채널명)·
    #   세로 그라데이션이어도(훅 회색 띠) 끝은 띠 색이다. 제목 글자 행은 끝이 바탕이라 띠가 아니다(첫 판은 '주된 색 비율'로 재
    #   흰 제목 줄을 흰 띠로 오판했다, 2026-10-16).
    band_rows = np.zeros(H, bool)
    row_color = {}
    for y in range(H):
        if not keep[y]:
            continue
        lft, rgt = np.median(a[y, :EDGE], axis=0), np.median(a[y, W - EDGE:], axis=0)
        if np.abs(lft - rgt).max() <= 24 and np.abs(lft - np.array(bg)).max() > DIFF:
            band_rows[y] = True
            row_color[y] = [int(v) for v in np.median(a[y], axis=0)]   # 띠 색 = 행 중앙값(가로 그라데이션 띠는 끝이 더 어둡다 — 훅 회색 띠 끝 160·가운데 235)
    runs = []
    for y0, y1 in _runs(band_rows, 1):
        col = [int(v) for v in np.median(np.array([row_color[y] for y in range(y0, y1 + 1)]), axis=0)]
        thin_dark = y1 - y0 + 1 <= 4 and sum(col) < 200
        runs.append([y0, y1, col, thin_dark])
    for y0, y1, col, thin_dark in runs:
        # 띠 면이 고른가 — 띠 색에서 40 안인 점이 절반 넘어야 띠(영상 가장자리가 비친 줄은 색이 흩어져 빠진다)
        rc = np.array([row_color[y] for y in range(y0, y1 + 1)])[:, None, :]   # 행마다 그 행의 색(세로 그라데이션 띠)
        flat = float((np.abs(a[y0:y1 + 1] - rc).max(axis=2) <= 60).mean())
        if not thin_dark and flat < 0.5:
            continue
        (dividers if thin_dark else bands).append({"y": y0, "h": y1 - y0 + 1, "rgb": col})
    # 바탕과 조금만 다른 띠(훅 머리 띠 56,58,51 vs 바탕 64 — 차 13, DIFF 40 아래라 위에서 빠졌다): 양 끝이 같은 색이고 바탕과
    #   LOW_DIFF 넘게 다르며 행의 60% 이상이 그 색인 행이 LOW_MIN_H 줄 넘게 같은 색으로 이어지면 띠.
    low = np.zeros(H, bool)
    for y in range(H):
        if not keep[y] or band_rows[y]:
            continue
        lft, rgt = np.median(a[y, :EDGE], axis=0), np.median(a[y, W - EDGE:], axis=0)
        if np.abs(lft - rgt).max() <= 6 and np.abs(lft - np.array(bg)).max() > LOW_DIFF \
                and float((np.abs(a[y] - lft).max(axis=1) <= 12).mean()) >= 0.6:
            low[y] = True
            row_color[y] = [int(v) for v in lft]
    for y0, y1 in _runs(low, LOW_MIN_H):
        cols = np.array([row_color[y] for y in range(y0, y1 + 1)])
        if (cols.max(axis=0) - cols.min(axis=0)).max() <= 10:
            bands.append({"y": y0, "h": y1 - y0 + 1, "rgb": [int(v) for v in np.median(cols, axis=0)], "low": True})
            band_rows[y0:y1 + 1] = True
    bands.sort(key=lambda b: b["y"])
    for b in bands:
        _band_paint(a, b, bg, keep, W)
    # 글자·상자: 띠 안은 띠 색(가로 그라데이션이면 칸마다 그 색) 기준, 밖은 바탕 기준. 어두운 띠 위 검정 선 그림(훅 머리 띠의 » ·
    #   포크 접시)은 띠와 차가 56 뿐이라 INK 80 으로는 안 보인다 → 어두운 띠(가장 밝은 채널 < 120) 안은 INK_DARK_BAND.
    local = np.tile(np.array(bg, dtype=int), (H, W, 1))
    thr = np.full(H, INK)
    for b in bands:
        prof = b.pop("_profile") if "_profile" in b else np.tile(np.array(b["rgb"], dtype=int), (W, 1))
        ft, fb = b.get("fade") or (0, 0)
        for y in range(b["y"], b["y"] + b["h"]):
            # 번진 줄은 바탕과 띠 사이(그 줄 밝기 비율만큼) — 아니면 번진 줄 전체가 글자로 잡힌다
            r = 1.0
            if y < b["y"] + ft:
                r = (y - b["y"] + 0.5) / max(1, ft)
            elif y >= b["y"] + b["h"] - fb:
                r = (b["y"] + b["h"] - y - 0.5) / max(1, fb)
            local[y] = np.round(np.array(bg) + r * (prof - np.array(bg))).astype(int) if r < 1 else prof
        band_rows[b["y"]:b["y"] + b["h"]] = True
        if max(b["rgb"]) < 120:
            thr[b["y"]:b["y"] + b["h"]] = INK_DARK_BAND
    ink = np.abs(a - local).max(axis=2) > thr[:, None]
    for b in dividers:
        ink[b["y"]:b["y"] + b["h"]] = False
    ink[~keep] = False
    # 상자: 바탕과 다르지만 글자(진한 점)는 아닌 단색 덩어리
    soft = diff & ~ink & ~band_rows[:, None]
    soft[~keep] = False
    import cv2
    n, lab, stt, _ = cv2.connectedComponentsWithStats(soft.astype(np.uint8), 8)
    for k in range(1, n):
        x, y, w, h, area = stt[k]
        if 50 <= w <= 260 and 50 <= h <= 260 and area > 0.6 * w * h:
            boxes.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h), "rgb": [int(v) for v in np.median(a[lab == k], axis=0)]})
    # 글자 행 묶음 → 가로 덩어리
    pieces = []
    for y0, y1 in _runs(ink.any(axis=1), 6, gap=12):   # 큰 제목 한 줄 안 자모 사이 빈 행(6~10px)으로 쪼개지 않게
        cols = ink[y0:y1 + 1].any(axis=0)
        for x0, x1 in _runs(cols, 3, gap=SPLIT_GAP):
            # 가로 덩어리 안을 다시 세로로 가른다(프로필 칸: 이름 줄 + 날짜 줄이 한 행 묶음에 들어온다)
            for r0, r1 in _runs(ink[y0:y1 + 1, x0:x1 + 1].any(axis=1), 6, gap=max(12, int(0.15 * (y1 - y0 + 1)))):   # 큰 글자 한 줄 안의 빈 행(자모 사이)으로 쪼개지 않게
                yy0, yy1 = y0 + r0, y0 + r1
                sub = ink[yy0:yy1 + 1, x0:x1 + 1]
                xs = np.where(sub.any(axis=0))[0]
                col = [int(v) for v in np.median(a[yy0:yy1 + 1, x0:x1 + 1][sub], axis=0)]
                inband = any(b["y"] <= yy0 and yy1 <= b["y"] + b["h"] for b in bands)
                pieces.append({"x0": int(x0 + xs.min()), "x1": int(x0 + xs.max()), "y0": int(yy0), "y1": int(yy1), "rgb": col, "in_band": inband})
    # 같은 높이·같은 색 덩어리가 글자 키의 0.6배 안으로 붙어 있으면 한 줄(큰 제목의 낱말 사이 띄어쓰기 ≈ 50px)
    pieces.sort(key=lambda t: (t["y0"], t["x0"]))
    for t in pieces:
        prev = texts[-1] if texts else None
        if prev:
            ov = min(prev["y1"], t["y1"]) - max(prev["y0"], t["y0"])
            hmax = max(prev["y1"] - prev["y0"], t["y1"] - t["y0"]) + 1
            if (ov >= 0.7 * hmax and 0 < t["x0"] - prev["x1"] < 0.6 * hmax
                    and max(abs(p - q) for p, q in zip(prev["rgb"], t["rgb"])) <= 40):
                prev.update(x1=t["x1"], y0=min(prev["y0"], t["y0"]), y1=max(prev["y1"], t["y1"]))
                continue
        texts.append(dict(t))
    for y0, y1 in ext:                               # 늘린 창 줄의 글자 덩어리는 영상 내용이다
        texts = [t for t in texts if not (t["y0"] >= y0 - 2 and t["y1"] <= y1 + 2)]
    return {"bg": bg, "bands": bands, "dividers": dividers, "boxes": boxes, "texts": texts, "video_ext": ext, "_ink": ink}


def _ocr_texts(frame: dict | None) -> list[list]:
    """예전 설명서의 [y 중심, 글, 역할, 정렬, 기준 x, 썼나] — 제목 여러 줄은 줄마다."""
    out = []
    for l in schema.all_layers(schema.validate(frame)) if frame else []:
        if l["kind"] != "text" or not l.get("text"):
            continue
        for n, line in enumerate(l["text"].split(NL)):
            out.append([l["y"] + (n + 0.5) * l["line_h"], line, l["role"], l["align"], l["x"], False])
    return out


def _match(texts, yc, x0=None, x1=None) -> tuple[str, str] | tuple[None, None]:
    """y 가 가깝고(OCR_MATCH_PX 안) 정렬 기준 x 가 가까운 글 — 한 번 쓴 글은 다시 안 쓴다(헤더 덩어리 둘이 같은 글을 받던 것)."""
    def cost(t):
        dx = 0 if x0 is None else abs({"center": (x0 + x1) / 2, "left": x0, "right": x1}[t[3]] - t[4])
        return abs(t[0] - yc) + 0.3 * dx
    cands = [t for t in texts if not t[5] and abs(t[0] - yc) <= OCR_MATCH_PX]
    best = min(cands, key=cost, default=None)
    if best is None:
        return None, None
    best[5] = True
    return best[1], best[2]


def _align(x0, x1, W) -> dict:
    c = (x0 + x1) / 2
    if abs(c - W / 2) <= 30:
        return {"x": W // 2, "w": W - 80, "align": "center"}
    if x0 < W * 0.35:
        return {"x": x0, "w": W - x0 - 40, "align": "left"}
    return {"x": x1, "w": x1 - 40, "align": "right"}


def text_layers(an: dict, ocr: list, W: int, font_default: str, notes: list, fid: str) -> list:
    """글자 덩어리 → 글자 층. 큰 글자가 2줄 이상 이어지면 제목(줄마다 색), 나머지는 label(글은 OCR 이어 쓰기)."""
    out = []
    # 제목 = 띠 밖의 큰 글자(높이 100px 이상) 두 줄이 위아래로 붙어 있을 때(틈 < 큰 쪽 높이의 0.6)
    cand = sorted([t for t in an["texts"] if t["y1"] - t["y0"] + 1 >= 100 and not t.get("in_band")], key=lambda t: t["y0"])
    big = []
    for p, q in zip(cand, cand[1:]):
        if q["y0"] - p["y1"] < 0.6 * max(p["y1"] - p["y0"], q["y1"] - q["y0"]):
            big = [p, q]; break
    used = set()
    if len(big) >= 2:
        texts = [_match(ocr, (t["y0"] + t["y1"]) / 2, t["x0"], t["x1"])[0] for t in big]
        fam = font_default
        if all(texts):
            fam = _font_for(an, big, texts, font_default)
        line_h = big[1]["y0"] - big[0]["y0"]
        fits = [T.size_and_top(fam, texts[i], b["y0"], b["y1"] - b["y0"] + 1, line_h) for i, b in enumerate(big)]
        x0, x1 = min(b["x0"] for b in big), max(b["x1"] for b in big)
        out.append({"kind": "text", "role": "title", **_align(x0, x1, W), "y": round(st.mean(f["y"] - i * line_h for i, f in enumerate(fits))),
                    "lines": 2, "font": fam, "size": round(st.mean(f["size"] for f in fits), 1), "line_h": line_h,
                    "rgb": big[0]["rgb"], "line_rgb": [b["rgb"] for b in big], "outline": None, "shadow": None, "box": None,
                    "italic": False, "letter_spacing": 0, "enter": None, "text": "\n".join(t or "" for t in texts) if all(texts) else None})
        used.update(id(b) for b in big)
        if not all(texts):
            notes.append(f"{fid}: 제목 글 OCR 이음 실패 → text null")
    # 덩어리 ↔ 예전 글을 전체에서 비용이 낮은 짝부터(먼저 나온 덩어리가 남의 글을 가져가지 않게 — 헤더 🍽 아이콘이 채널명 글을 받던 것)
    rest = [t for t in an["texts"] if id(t) not in used]
    pairs = []
    for t in rest:
        for o in ocr:
            if o[5] or abs(o[0] - (t["y0"] + t["y1"]) / 2) > OCR_MATCH_PX:
                continue
            dx = abs({"center": (t["x0"] + t["x1"]) / 2, "left": t["x0"], "right": t["x1"]}[o[3]] - o[4])
            pairs.append((abs(o[0] - (t["y0"] + t["y1"]) / 2) + 0.3 * dx, id(t), o))
    got = {}
    for c, tid, o in sorted(pairs, key=lambda p: p[0]):
        if tid in got or o[5]:
            continue
        got[tid] = o[1]; o[5] = True
    import re
    jobs, free = [], [t for t in rest if not got.get(id(t))]
    for t in rest:
        txt = got.get(id(t))
        if not txt:
            continue
        head, tail = re.match(SYM_RE_HEAD, txt), None
        runs = _split_runs(an, t)
        if head and len(runs) >= 2:                       # 앞 기호가 같은 덩어리에 붙어 있다 → 첫 잉크 묶음이 기호
            jobs.append((_sub_piece(an, t, *runs[0]), head.group(1), True))
            t = _sub_piece(an, t, runs[1][0], runs[-1][1]); txt = head.group(2); runs = runs[1:]
        tail = re.match(SYM_RE_TAIL, txt)
        if tail:
            # 뒤 기호가 떨어져 따로 잡힌 덩어리(같은 줄 오른쪽, 글 안 받은 것)가 먼저 — 없을 때만 덩어리의 마지막 잉크 묶음
            #   (낱말 사이 띄어쓰기도 SYM_GAP 을 넘어 '친구들'을 🍽 로 떼어 낸 적이 있다)
            right = [f for f in free if f["x0"] > t["x1"] and min(f["y1"], t["y1"]) - max(f["y0"], t["y0"]) > 0.5 * (t["y1"] - t["y0"])]
            if right:
                r0 = min(right, key=lambda f: f["x0"]); free.remove(r0)
                jobs.append((r0, tail.group(2), True)); txt = tail.group(1)
            elif len(runs) >= 2 and runs[-1][0] - runs[-2][1] > SYM_GAP:
                jobs.append((_sub_piece(an, t, *runs[-1]), tail.group(2), True))
                t = _sub_piece(an, t, runs[0][0], runs[-2][1]); txt = tail.group(1)
        jobs.append((t, txt, False))
    for t in free:
        notes.append(f"{fid}: 글자 덩어리 y{t['y0']}~{t['y1']} x{t['x0']}~{t['x1']} — OCR 이을 글 없음 → 층 생략")
    for t, txt, is_sym in jobs:
        if is_sym or re.fullmatch(r"[^\w\s]+", txt):
            fam = _sym_font(an, t, txt, font_default)
            f = _sym_size(fam, txt, t["y0"], t["y1"] - t["y0"] + 1)
            notes.append(f"{fid}: 기호 {txt!r} 따로 층 — 잉크 {t['x0']}~{t['x1']}×{t['y0']}~{t['y1']}, 글꼴 {fam}, 잰 글꼴 {f.get('measured_by')}")
            out.append({"kind": "text", "role": "label", **_align(t["x0"], t["x1"], W), "y": f["y"], "lines": 1, "font": fam,
                        "size": f["size"], "line_h": f["line_h"], "rgb": t["rgb"], "line_rgb": None, "outline": None, "shadow": None,
                        "box": None, "italic": False, "letter_spacing": 0, "enter": None, "text": txt,
                        "_target": [t["x0"], t["y0"], t["x1"], t["y1"]]})
            continue
        fam = _font_for(an, [t], [txt], font_default)
        f = T.size_and_top(fam, txt, t["y0"], t["y1"] - t["y0"] + 1, None)
        out.append({"kind": "text", "role": "label", **_align(t["x0"], t["x1"], W), "y": f["y"], "lines": 1, "font": fam,
                    "size": f["size"], "line_h": f["line_h"], "rgb": t["rgb"], "line_rgb": None, "outline": None, "shadow": None,
                    "box": None, "italic": False, "letter_spacing": T.spacing_for(fam, f["size"], txt, t["x1"] - t["x0"] + 1) or 0,
                    "enter": None, "text": txt})
    return out



# ── 기호 낱개(헤더 » · 🍽) ─────────────────────────────────────────────────────────────────────────────
# 글 앞뒤의 기호(낱말 글자가 아닌 것)는 그 덩어리 안 자기 잉크 크기로 따로 층을 만든다 — 한 층에 같이 두면 기호가 글 크기를 따라
#   원본보다 작게 나왔다(rGFX 머리 띠: 원본 » 107px·🍽 108px 높이 vs 우리 61/54px, 2026-10-16).
SYM_RE_HEAD = r"^([^\w\s]+)\s+(.+)$"
SYM_RE_TAIL = r"^(.+?)\s+([^\w\s]+)$"
SYM_GAP = 20          # 기호와 글 사이 가로 틈(px) — 이 넘는 틈으로 덩어리를 가른다
EMOJI_FALLBACK = ("C:/Windows/Fonts/seguiemj.ttf", "C:/Windows/Fonts/seguisym.ttf",
                  "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")


def _has_glyph(font, ch: str) -> bool:
    """빈 글자 상자(.notdef)와 다르면 있다. 비교 글자는 U+0378(쓰이지 않는 자리) — U+F0000 은 Pretendard 에 그림이 있어(10-16 실측)
    이모지 없는 Pretendard 가 🍽 이 '있다'고 나왔다."""
    return font.getmask(ch).getbbox() != font.getmask(chr(0x378)).getbbox()


def _sym_font(an, piece, sym: str, default: str) -> str:
    """기호 글꼴 — fontmatch 순위에서 그 기호가 있는 첫 등록 글꼴(점수 문턱 없음: 기호는 글자 수가 적어 점수가 낮다). 없으면 기본."""
    try:
        from tools.calcopy.engine import fontmatch
        img = an["_img"]
        crop = img[max(0, piece["y0"] - 4):piece["y1"] + 5, max(0, piece["x0"] - 4):piece["x1"] + 5].astype(int)
        border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
        bgc = np.median(border, axis=0)
        # 잉크 색에 더 가까운 점 — 어두운 띠(56) 위 검정 선은 '잉크 색에서 70 안'으로 재면 띠까지 잉크가 돼 굵은 글꼴이 뽑혔다
        mask = np.abs(crop - np.array(piece["rgb"])).max(axis=2) < np.abs(crop - bgc).max(axis=2)
        for r in fontmatch.rank(mask, sym)[:30]:
            fam = T.family_of(r["font"])
            if fam and r["score"] > 0 and all(_has_glyph(T._pil_font(fam, 100), c) for c in sym):
                return fam
    except Exception as e:  # noqa: BLE001
        print("sym_font 실패:", e)
    return default


def _sym_size(fam: str, sym: str, ink_top: float, ink_h: float) -> dict:
    """기호 잉크 높이·위 끝 → 크기·줄 칸 y. 그 글꼴에 없는 기호(이모지)는 렌더러가 시스템 글꼴로 대신 그린다 — 같은 대신 글꼴로 잰다
    (윈도 Segoe UI Emoji / 리눅스 Noto Color Emoji — 서버와 이 PC의 대신 글꼴이 다르면 크기가 다를 수 있다)."""
    from PIL import ImageFont
    f100 = T._pil_font(fam, 100)
    meas = f100 if all(_has_glyph(f100, c) for c in sym) else None
    path = None
    if meas is None:
        for p in EMOJI_FALLBACK:
            if Path(p).exists():
                try:
                    meas = ImageFont.truetype(p, 109 if "Color" in p else 100); path = p; break
                except OSError:
                    continue
    if meas is None:
        return T.size_and_top(fam, sym, ink_top, ink_h, None) | {"measured_by": "없음"}
    base = 109 if path and "Color" in path else 100
    b = meas.getbbox(sym, anchor="ls")
    size = ink_h * base / max(1, b[3] - b[1])
    asc, desc = T._pil_font(fam, size).getmetrics()
    bt = b[1] * size / base
    lh = round(size * 1.15)
    y = ink_top - ((lh - (asc + desc)) / 2 + asc + bt)
    return {"size": round(size, 1), "y": round(y), "line_h": lh, "measured_by": Path(path).name if path else fam}


def _split_runs(an, t) -> list[tuple[int, int]]:
    ink = an["_ink"][t["y0"]:t["y1"] + 1, t["x0"]:t["x1"] + 1].any(axis=0)
    return [(t["x0"] + a, t["x0"] + b) for a, b in _runs(ink, 1, gap=SYM_GAP - 1)]


def _sub_piece(an, t, x0, x1) -> dict:
    sub = an["_ink"][t["y0"]:t["y1"] + 1, x0:x1 + 1]
    ys = np.where(sub.any(axis=1))[0]
    return {**t, "x0": x0, "x1": x1, "y0": t["y0"] + int(ys.min()), "y1": t["y0"] + int(ys.max())}


def _font_for(an, blocks, texts, default) -> str:
    """덩어리 글꼴 — fontmatch.rank(분석기와 같은 판별 함수)로 1위 등록 글꼴. 못 하면 기본(자막 글꼴)."""
    try:
        from tools.calcopy.engine import fontmatch
        img = an["_img"]
        tot = {}
        for b, t in zip(blocks, texts):
            crop = img[max(0, b["y0"] - 4):b["y1"] + 5, max(0, b["x0"] - 4):b["x1"] + 5].astype(int)
            mask = np.abs(crop - np.array(b["rgb"])).max(axis=2) < 70
            for x in fontmatch.rank(mask, t)[:8]:
                tot[x["font"]] = tot.get(x["font"], 0) + x["score"]
        for f, sc in sorted(tot.items(), key=lambda kv: -kv[1]):
            fam = T.family_of(f)
            if fam:
                return fam if sc / max(1, len(blocks)) >= FONT_MIN else default

    except Exception as e:  # noqa: BLE001 — 판별 실패는 기본 글꼴로, 이유는 부르는 쪽 notes 에 안 남기고 여기서 출력
        print("font_for 실패:", e)
    return default


def build_multi(J: dict, src: str, ocr_from: dict | None = None, calibrate: bool = True) -> dict:
    from shopping_shorts.channelkit.bench import probe
    notes = []
    pr = J.get("probe") or {}
    W, H = int(pr.get("w") or 1080), int(pr.get("h") or 1920)
    dur = float(pr.get("duration") or 0)
    L = J.get("layout") or {}
    others = sorted(L.get("other_frame_segments") or [])
    shots = ((J.get("cuts") or {}).get("picture_boxes") or {}).get("per_shot") or []
    cap = J.get("captions") or {}
    items = cap.get("items") or []
    fam_cap, _ = T.pick_font(J.get("fonts"))
    spans, t = [], 0.0
    for a, b in others:
        if b >= dur - 0.3:
            continue                          # 꼬리 구간은 template_off 몫
        if a > t + 0.05:
            spans.append(("body", t, a))
        spans.append(("hook" if a < 0.05 else f"seg{len(spans)}", a, b)); t = b
    spans.append(("body", t, None))
    frames = []
    for fid, a, b in spans:
        end = b if b is not None else dur
        sh = [s for s in shots if s["t"][0] < end - 0.01 and s["t"][1] > a + 0.01]
        # 표본 시각: 그 구간에서 자막이 한 줄 이상인 첫 장면 가운데(본문) / 구간 가운데(훅)
        it = next((i for i in items if i["t0"] >= a - 0.01 and (b is None or i["t1"] <= b + 0.01) and i.get("lines", 0) >= 1 and i["t0"] > 0.05), None)
        ts = (it["t0"] + it["t1"]) / 2 if (fid == "body" and it) else (a + end) / 2
        img = probe.grab(src, ts, f"scale={W}:{H}", W, H)
        sh_now = next((s for s in sh if s["t"][0] <= ts < s["t"][1]), sh[0] if sh else None)
        vrect = sh_now["box"] if sh_now else None
        cap_items = [i for i in items if i["t0"] >= a - 0.01 and (b is None or i["t1"] <= b + 0.01)]
        skip = []
        if fid == "body" and cap.get("region"):
            band = L.get("caption_band") or cap["region"]
            skip.append((band[0] - 6, band[1] + 6))
        t2 = a + 0.2 * (end - a) if abs(ts - (a + 0.2 * (end - a))) > 0.3 else a + 0.8 * (end - a)
        img2 = probe.grab(src, t2, f"scale={W}:{H}", W, H)       # 같은 틀 다른 시각 — 움직이면 영상, 가만히 있으면 틀
        an = analyze_image(img, skip, vrect, img2)
        an["_img"] = img
        layers = [{"kind": "bg", "rgb": an["bg"]}]
        if sh:
            base = sh_now["box"]
            v = {"kind": "video", "x": base[0], "y": base[1], "w": base[2], "h": base[3], "radius": 0}
            for y0, y1 in an.get("video_ext") or []:   # 창에 붙어 이어지는 영상 줄만큼 창을 늘린다
                if y0 >= v["y"] + v["h"] - 4:
                    v["h"] = y1 + 1 - v["y"]
                elif y1 + 1 <= v["y"] + 4:
                    v["h"] += v["y"] - y0; v["y"] = y0
            if an.get("video_ext"):
                notes.append(f"{fid}: 뜯기 그림 칸 {base} 에 붙은 영상 줄 {an['video_ext']} 까지 창을 늘림 → y{v['y']} h{v['h']}")
            if len(sh) > 1:
                v["cuts"] = [{"t": [max(a, s["t"][0]), min(end, s["t"][1])], "w": s["box"][2], "h": s["box"][3],
                              "x": s["box"][0], "y": s["box"][1]} for s in sh]
            layers.append(v)
        for bnd in an["bands"]:
            layers.append({"kind": "band", "x": 0, "y": bnd["y"], "w": W, "h": bnd["h"], "rgb": bnd["rgb"], "radius": 0,
                           **{k: bnd[k] for k in ("grad_x", "fade") if k in bnd}})
        for d in an["dividers"]:
            layers.append({"kind": "band", "x": 0, "y": d["y"], "w": W, "h": d["h"], "rgb": d["rgb"], "radius": 0})
        for bx in an["boxes"]:
            layers.append({"kind": "band", **{k: bx[k] for k in ("x", "y", "w", "h")}, "rgb": bx["rgb"], "radius": 0})
        ocr = _ocr_texts((ocr_from or {}).get(fid))
        layers += text_layers(an, ocr, W, fam_cap or "BMDOHYEON", notes, fid)
        if fid == "body" and cap_items and fam_cap:
            ly = [i["top_y"] for i in cap_items if i.get("top_y") is not None]
            lead = [i["leading"] for i in cap_items if i.get("leading")]
            lines = max(int(i.get("lines") or 1) for i in cap_items)
            ink_h = (J.get("text_fx") or {}).get("summary", {}).get("line_h_px") or st.median(g["line_h"] for g in cap.get("glyph") or [{"line_h": 50}])
            first = next((i["text"][0] for i in cap_items if i.get("text")), None)
            line_h = round(st.median(lead)) if lead else None
            f = T.size_and_top(fam_cap, first, st.median(ly), ink_h, line_h)
            accum = any(int(i.get("lines") or 1) > 1 for i in cap_items) and any(int(i.get("lines") or 1) == 1 for i in cap_items)
            layers.append({"kind": "text", "role": "caption", "x": W // 2, "w": W - 80, "align": "center", "y": f["y"], "lines": lines,
                           "font": fam_cap, "size": f["size"], "line_h": f["line_h"], "rgb": [0, 0, 0], "line_rgb": None,
                           "outline": None, "shadow": None, "box": None, "italic": False, "letter_spacing": 0,
                           "valign": "top" if accum else "center", "enter": None})
            if accum:
                notes.append(f"{fid}: 누적형 자막(1줄·2줄이 섞임) → valign top, 줄 칸 {f['line_h']}")
            # 그림 칸이 자막 아래에 붙는 간격 — 컷마다 (그림 y − 그 시각 자막 줄 수 × 줄높이 − 자막 칸 위) 의 중앙값
            gaps = []
            for s in sh:
                mid = (s["t"][0] + s["t"][1]) / 2
                ci = next((i for i in cap_items if i["t0"] <= mid < i["t1"]), None)
                if ci:
                    gaps.append(s["box"][1] - (f["y"] + int(ci.get("lines") or 1) * f["line_h"]))
            if gaps and any(l.get("kind") == "video" for l in layers):
                v = next(l for l in layers if l["kind"] == "video")
                v["anchor"] = {"below": "caption", "gap": round(st.median(gaps))}
                notes.append(f"{fid}: 그림 칸 자막 아래 간격 중앙값 {round(st.median(gaps))}px (컷별 y 가 있으면 그 값이 먼저)")
        frames.append({"id": fid, "span": [a, b], "layers": layers[:schema.MAX_LAYERS]})
        if len(layers) > schema.MAX_LAYERS:
            notes.append(f"{fid}: 층 {len(layers)}개 → 상한 {schema.MAX_LAYERS}개로 자름")
    if calibrate:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            calibrate_symbols({"canvas": [W, H], "frames": frames, "template_off": None, "made_by": schema.MADE_BY}, Path(td), notes)
    else:
        for fr in frames:
            for l in fr["layers"]:
                l.pop("_target", None)
    out = {"canvas": [W, H], "frames": frames, "template_off": None, "made_by": schema.MADE_BY,
           "source": Path(str(J.get("source") or "")).stem or None,
           "made_from": {"tool": "tools/calcopy/engine/to_frame_multi.py", "engine": J.get("engine"), "notes": notes}}
    return out



# ── 기호 크기 맞추기(렌더러로 재서) ───────────────────────────────────────────────────────────────────────
# 기호는 등록 글꼴에 없으면 렌더러(크롬)가 시스템 글꼴로 대신 그린다 — PIL 로 잰 크기와 실제 그림이 다르다(🍽: Segoe UI Emoji 로 재
#   121px 로 정했는데 렌더 높이 75px, 원본 108px, 2026-10-16). 그래서 실제 렌더(render_layer_one — 편집 화면·렌더·썸네일과 같은 길)로
#   한 번 그려 잉크 상자를 재고, 높이 비율로 크기를, 다시 그려 위 끝·정렬 끝을 맞춘다.
CAL_PAD = 30           # 기호 잉크를 찾을 때 원본 상자 바깥 여유(px)
CAL_INK = 35


def _render_frame(F: dict, t: float, work: Path) -> np.ndarray:
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    from PIL import Image
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(F))
    spec = schema.validate(F)
    title = next((l for l in schema.all_layers(spec) if l["kind"] == "text" and l["role"] == "title"), None)
    head = {"text": (title or {}).get("text") or ""}
    tl = [{"beat_idx": 0, "t0": 0, "dur": max(0.05, t), "narration": "", "caption_lines": [], "role": "hook",
           "primary": {"video_id": "s0", "start": 0, "end": max(0.05, t)}},
          {"beat_idx": 1, "t0": max(0.05, t), "dur": 1.0, "narration": "", "caption_lines": [], "role": "body",
           "primary": {"video_id": "s0", "start": max(0.05, t), "end": max(0.05, t) + 1}}]
    png = scene_style.render_layer_one(tl, snap, work, 1, head)
    im = Image.open(png).convert("RGBA")
    base = Image.new("RGBA", im.size, (0, 0, 0, 255))
    return np.asarray(Image.alpha_composite(base, im).convert("RGB")).astype(int)


def _ink_box(img: np.ndarray, box) -> list | None:
    x0, y0, x1, y1 = box
    H, W = img.shape[:2]
    X0, Y0, X1, Y1 = max(0, x0 - CAL_PAD), max(0, y0 - CAL_PAD), min(W - 1, x1 + CAL_PAD), min(H - 1, y1 + CAL_PAD)
    reg = img[Y0:Y1 + 1, X0:X1 + 1]
    border = np.concatenate([reg[0], reg[-1], reg[:, 0], reg[:, -1]])
    m = np.abs(reg - np.median(border, axis=0)).max(axis=2) > CAL_INK
    if not m.any():
        return None
    ys, xs = np.where(m.any(axis=1))[0], np.where(m.any(axis=0))[0]
    return [X0 + int(xs.min()), Y0 + int(ys.min()), X0 + int(xs.max()), Y0 + int(ys.max())]


def _strip(F: dict) -> dict:
    return {**F, "frames": [{**x, "layers": [{k: v for k, v in l.items() if k != "_target"} for l in x["layers"]]} for x in F["frames"]]}


def calibrate_symbols(F: dict, work: Path, notes: list) -> None:
    """F 의 기호 층(_target = 원본 잉크 상자 [x0,y0,x1,y1] 이 붙은 글자 층)을 렌더 실측으로 크기·자리 맞춤. 끝나면 _target 을 지운다."""
    for fr in F["frames"]:
        syms = [l for l in fr["layers"] if l.get("_target")]
        if not syms:
            continue
        t = fr["span"][0] + 0.1
        try:
            for step in ("size", "place", "check"):
                img = _render_frame(_strip(F), t, work / f"{fr['id']}_{step}")
                for l in syms:
                    tg = l["_target"]
                    got = _ink_box(img, tg)
                    if got is None:
                        notes.append(f"{fr['id']}: 기호 {l['text']!r} 렌더에서 못 찾음({step})")
                        continue
                    if step == "size":
                        l["size"] = round(l["size"] * (tg[3] - tg[1] + 1) / max(1, got[3] - got[1] + 1), 1)
                        l["line_h"] = round(l["size"] * 1.15)
                    elif step == "place":
                        l["y"] = round(l["y"] + tg[1] - got[1])
                        if l["align"] == "left":
                            l["x"] = round(l["x"] + tg[0] - got[0])
                        elif l["align"] == "right":
                            l["x"] = round(l["x"] + tg[2] - got[2])
                    else:
                        notes.append(f"{fr['id']}: 기호 {l['text']!r} 렌더 실측 맞춤 — 원본 상자 {tg} / 우리 {got} "
                                     f"(높이 차 {(got[3] - got[1]) - (tg[3] - tg[1])}px, 위 끝 차 {got[1] - tg[1]}px)")
        except Exception as e:  # noqa: BLE001 — 렌더러(node)가 없는 곳: 맞춤 없이 PIL 크기 그대로, 이유는 notes 에
            notes.append(f"{fr['id']}: 기호 렌더 맞춤 못 함 — {str(e)[:160]}")
    for fr in F["frames"]:
        for l in fr["layers"]:
            l.pop("_target", None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("tteutgi"); ap.add_argument("--out", required=True)
    ap.add_argument("--ocr-from", nargs="*", default=[], help="틀이름=frame.json (예 hook=a.json body=b.json)")
    ap.add_argument("--no-calibrate", action="store_true", help="기호 크기를 렌더 실측으로 맞추지 않는다(렌더러 node 가 없는 곳)")
    a = ap.parse_args(argv)
    J = json.loads(Path(a.tteutgi).read_text(encoding="utf-8"))
    ocr = {}
    for kv in a.ocr_from:
        k, p = kv.split("=", 1)
        ocr[k] = json.loads(Path(p).read_text(encoding="utf-8"))
    F = build_multi(J, J["source"], ocr, calibrate=not a.no_calibrate)
    schema.validate(F)
    Path(a.out).write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(F["made_from"], ensure_ascii=False, indent=1))
    print("frame:", a.out)


if __name__ == "__main__":
    main()
