# -*- coding: utf-8 -*-
"""글꼴 대조 — tools/hotpeople/measure/font.py·font4.py 원리를 함수로(경로 하드코딩 제거).

원리: 원본 자막 한 줄의 잉크(bench layout.ink_mask)를 bbox로 자르고, 후보 글꼴로 **같은 글자**를 그려 잉크 bbox로
자른 뒤, 낱말 사이 빈 열을 접고(받아쓴 띄어쓰기가 틀려도 흔들리지 않게), 후보를 원본 bbox 크기로 늘려(폭·높이 맞춤)
겹침(IoU)을 잰다. 폭을 억지로 맞춘 만큼 종횡비 벌점, 획 굵기가 다른 만큼 잉크 밀도 벌점을 곱한다.
  score = IoU × max(0, 1 − |종횡비비 − 1|) × max(0, 1 − |밀도차|/원본밀도)   method = METHOD
  (2026-10-15 썰풀다 실측: 접기 전엔 OCR "아무데나"↔화면 "아무 데나" 띄어쓰기 차이로 뚱뚱한 글꼴이 1위였다)
후보 창고: shopping_shorts/static/fonts + channel_presets/brainbulb/fonts (같은 파일명은 하나만).
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from shopping_shorts.channelkit.bench import layout
from shopping_shorts.channelkit.bench import constants as C

ROOT = Path(__file__).resolve().parents[3]
FONT_DIRS = [ROOT / "shopping_shorts" / "static" / "fonts", ROOT / "shopping_shorts" / "channel_presets" / "brainbulb" / "fonts"]
METHOD = "gap_collapse+bbox_fit_iou×aspect×density"
RENDER_PX = 120          # 후보 그리는 글자 크기(font.py 와 같음)
LINE_FRAG_FRAC = 0.4     # 줄 높이가 가장 높은 줄의 40% 미만이면 조각으로 버린다
FILL_LUM_MIN = 110       # 어두운 단색 바탕에서 밝은 글자 채움 문턱(그 밖엔 INK_BRIGHT)
BIG_FRAC = 0.15         # 밝은 덩어리가 크롭 넓이의 15% 넘으면 글자가 아니라 배경
OUTLINED_FRAC = 0.6      # 밝은 덩어리 둘레의 60% 이상이 외곽선 옆이어야 글자 채움
SPECK_PX = 12            # 이보다 작은 잉크 덩어리는 티끌로 버린다
LABEL_FONT = ROOT / "shopping_shorts" / "static" / "fonts" / "NanumGothic-Bold.ttf"


def font_paths() -> list[str]:
    seen, out = set(), []
    for d in FONT_DIRS:
        for p in sorted(glob.glob(str(d / "*.ttf")) + glob.glob(str(d / "*.otf"))):
            b = os.path.basename(p)
            if b not in seen:
                seen.add(b)
                out.append(p)
    return out


def _bbox(a: np.ndarray) -> np.ndarray | None:
    ys, xs = np.where(a)
    if len(ys) == 0:
        return None
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def glyph_mask(img: np.ndarray, pol: str) -> np.ndarray:
    """글자 **채움** 마스크. 씨앗 = bench layout.ink_mask(티끌 제거).
    밝은 글자(bright)는 bench 정의가 '외곽선 2px 안의 밝은 화소'라 굵은 획은 테두리 고리만 잡힌다
    (2026-10-16 mYxuF1A74j4 실측: 글꼴 점수 0.1 미만) → 밝은 화소(lum>INK_BRIGHT) 덩어리 중 씨앗에 닿는 것을 통째로 채운다.
    크롭 넓이의 BIG_FRAC 넘는 큰 덩어리(밝은 배경)는 뺀다."""
    seed = layout.ink_mask(img, pol).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(seed, 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= SPECK_PX
    seed = keep[lab]
    if pol != "bright":
        return seed
    L = layout.lum(img)
    # 단색 어두운 바탕(제목 띠 등, 중앙 밝기 ≤ 외곽선 문턱)에선 노랑(lum≈199) 채움도 담게 문턱을 낮춘다.
    # 영상 위 자막에선 낮추면 영상 속 밝은 곳이 글자에 붙는다(2026-10-16 mY 자막 c01 실측) → INK_BRIGHT 그대로.
    thr = FILL_LUM_MIN if float(np.median(L)) <= C.INK_OUTLINE_DARK else C.INK_BRIGHT
    bright = (L > thr).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(bright, 8)
    hit = np.zeros(n, bool)
    hit[np.unique(lab[seed])] = True
    hit[0] = False
    hit &= st[:, cv2.CC_STAT_AREA] < BIG_FRAC * img.shape[0] * img.shape[1]   # 밝은 배경 덩어리 제외(높이 기준은 꽉 낀 제목 크롭에서 글자를 버렸다)
    # 글자 채움은 둘레가 거의 다 외곽선(어두움)에 닿는다 — 영상 속 밝은 덩어리는 아니다
    k = 2 * C.INK_OUTLINE_R + 1
    near_dark = cv2.dilate((layout.lum(img) <= C.INK_OUTLINE_DARK).astype(np.uint8), np.ones((k, k), np.uint8)) > 0
    edge = (bright > 0) & ~(cv2.erode(bright, np.ones((3, 3), np.uint8)) > 0)
    tot = np.bincount(lab[edge], minlength=n)
    dark = np.bincount(lab[edge & near_dark], minlength=n)
    hit &= dark >= OUTLINED_FRAC * np.maximum(tot, 1)
    return hit[lab] | seed


def line_masks(img: np.ndarray, pol: str) -> list[np.ndarray]:
    """자막 크롭(RGB) → 줄별 글자 채움 마스크(bbox로 자름, 위→아래). 행 잉크 > GLYPH_ROW_PX 인 덩어리."""
    ink = glyph_mask(img, pol)
    bands = layout.segs(ink.sum(axis=1) > C.GLYPH_ROW_PX, min_len=C.GLYPH_FIRST_LINE_MIN, gap=4)
    out = []
    for s, e in bands:
        m = _bbox(ink[s:e])
        if m is not None and m.shape[1] >= 20:
            out.append(m)
    if out:   # 가장 높은 줄의 40% 미만 높이 = 위아래 띠·영상 가장자리 조각(2026-10-16 mY 제목 2줄째 24px 조각)
        hmax = max(m.shape[0] for m in out)
        out = [m for m in out if m.shape[0] >= LINE_FRAG_FRAC * hmax]
    return out


@lru_cache(maxsize=4096)
def _font(path: str, size: int):
    return ImageFont.truetype(path, size)


def missing_glyphs(path: str, text: str) -> list[str]:
    """글꼴에 없는 글자(.notdef 모양과 같으면 없음)."""
    f = _font(path, 40)

    def g(ch: str) -> bytes:
        im = Image.new("L", (64, 64), 0)
        ImageDraw.Draw(im).text((8, 4), ch, font=f, fill=255)
        return im.tobytes()

    notdef = g("\U000F0000")
    return [ch for ch in sorted(set(text)) if not ch.isspace() and g(ch) == notdef]


@lru_cache(maxsize=4096)
def render(path: str, text: str) -> np.ndarray | None:
    f = _font(path, RENDER_PX)
    l, t, r, b = f.getbbox(text)
    im = Image.new("L", (r - l + 40, b - t + 40), 255)
    ImageDraw.Draw(im).text((20 - l, 20 - t), text, font=f, fill=0)
    return _bbox(np.array(im) < 110)


GAP_FRAC = 0.2           # 줄 높이의 20% 넘는 빈 열 = 낱말 사이 → 접는다(받아쓴 띄어쓰기 오류·자간 차이에 흔들리지 않게)


def collapse_gaps(a: np.ndarray) -> np.ndarray:
    col = a.any(axis=0)
    keep = np.ones(a.shape[1], bool)
    for s, e in layout.segs(~col, min_len=max(2, int(GAP_FRAC * a.shape[0]))):
        keep[s:e] = False
    return a[:, keep]


def score(ref: np.ndarray, cand: np.ndarray) -> float:
    """빈 열 접기 → 후보를 원본 bbox 크기로 늘림 → IoU × 종횡비 벌점 × 잉크 밀도(획 굵기) 벌점."""
    ref, cand = collapse_gaps(ref), collapse_gaps(cand)
    H, W = ref.shape
    c = np.array(Image.fromarray((cand * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)) > 127
    iou = (ref & c).sum() / max(1, (ref | c).sum())
    ar = (cand.shape[1] / cand.shape[0]) / (W / H)
    dr = max(float(ref.mean()), 1e-6)
    return float(iou * max(0.0, 1.0 - abs(1.0 - ar)) * max(0.0, 1.0 - abs(float(c.mean()) - dr) / dr))


def rank(ref: np.ndarray, text: str, fonts: list[str] | None = None) -> list[dict]:
    """원본 한 줄 잉크 vs 후보 글꼴 전부. 글자 빠진 글꼴은 score 0 + missing."""
    out = []
    for p in fonts or font_paths():
        name = os.path.basename(p)
        try:
            miss = missing_glyphs(p, text)
            if miss:
                out.append({"font": name, "score": 0.0, "missing": "".join(miss[:5])})
                continue
            cand = render(p, text)
            out.append({"font": name, "score": round(score(ref, cand), 4) if cand is not None else 0.0})
        except Exception as e:  # noqa: BLE001 — 못 여는 글꼴은 표에 남긴다
            out.append({"font": name, "score": 0.0, "failed": str(e)[:60]})
    return sorted(out, key=lambda r: -r["score"])


def grid(ref: np.ndarray, text: str, top: list[dict], out_png: str, h: int = 70) -> None:
    """font4.py 꼴: 맨 위 원본, 아래 후보 상위 N(같은 높이)."""
    paths = {os.path.basename(p): p for p in font_paths()}
    rows = [Image.fromarray(((~ref) * 255).astype(np.uint8)).resize((max(1, int(ref.shape[1] * h / ref.shape[0])), h))]
    names = ["원본"]
    for r in top:
        a = render(paths[r["font"]], text)
        if a is None:
            continue
        rows.append(Image.fromarray(((~a) * 255).astype(np.uint8)).resize((max(1, int(a.shape[1] * h / a.shape[0])), h)))
        names.append(f"{r['font'][:24]} {r['score']:.3f}")
    W = max(x.width for x in rows) + 330
    out = Image.new("L", (W, len(rows) * (h + 14)), 255)
    d = ImageDraw.Draw(out)
    lab = ImageFont.truetype(str(LABEL_FONT), 20)
    for i, (im, n) in enumerate(zip(rows, names)):
        out.paste(im, (320, i * (h + 14)))
        d.text((5, i * (h + 14) + 22), n, font=lab, fill=0)
    out.save(out_png)


def slant_deg(mask: np.ndarray) -> float | None:
    """글자 기둥 기울기(도, +는 오른쪽으로 누움 = 기울임체). 각도마다 행을 밀어(전단) 세운 뒤 열 투영이 가장 날카로운 각.
    정자체 ≈ 0, 기울임 ≈ 8~15. 잉크가 너무 적으면 None."""
    if mask is None or mask.sum() < 200:
        return None
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    best = None
    for deg in range(-20, 21):
        sh = np.tan(np.radians(deg))
        cx = np.round(xs + (ys - h / 2) * sh).astype(int)     # 위쪽 행을 왼쪽으로 되밀어 세운다
        cx -= cx.min()
        col = np.bincount(cx)
        v = float((col.astype(np.float64) ** 2).sum())
        if best is None or v > best[0]:
            best = (v, deg)
    return float(best[1])
