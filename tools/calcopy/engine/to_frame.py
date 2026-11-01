# -*- coding: utf-8 -*-
"""뜯기 결과(뜯기.json, analyze.py) → 틀 설명서(frame.json, shopping_shorts/calcopy_frame/schema.py).

    PYTHONUTF8=1 py tools/calcopy/engine/to_frame.py <뜯기.json> --out frame.json [--no-ocr]

설계 docs/superpowers/specs/2026-10-15-칼카피엔진-design.md §5·§6-3. 판단 주인: 뜯기 값 → 설명서 값 매핑은 build() 한 곳.
재는 일은 analyze.py 가 했다 — 여기서 새로 재는 것은 뜯기.json 에 없는 셋뿐이고, 원본 영상 한 프레임에서 잰다:
  ① 창 위 고정 글자 띠의 가로 범위·색(뜯기엔 y 범위만 있다)  ② 제목·[광고] 글자(OCR — 뜯기엔 자막 OCR 만 있다)
  ③ 틀이 다른 구간의 정확한 시작(뜯기의 창 다수결은 약 6초 조각 단위라 17.92초로 나온다 — 0.1초 간격으로 다시 찾는다)
매핑 규칙:
  - 창 위 띠 중 화면 위 6% 안에서 시작하고 폭이 화면의 40% 미만인 것 = 고정 문구(brand, 예 [광고]), 나머지 = 제목 줄(위→아래)
  - 글자 크기 = 잉크 높이 ÷ (그 글꼴로 같은 글을 100px 로 그렸을 때 잉크 높이) × 100 — 글꼴마다 잉크 비율이 달라서 실제 글꼴로 잰다
  - 글꼴 = 뜯기 fonts 합산 순위에서 **장면꾸미기에 등록된** 첫 글꼴. 1위 점수 < 0.5 이면 font_confidence "low"
  - 틀이 다른 구간이 영상 끝까지 가면 template_off.tail_sec = 길이 − 그 구간 시작(다시 찾은 값)
  - 값이 없으면 null(0 은 값). 못 정한 것은 notes 에 적는다(조용히 기본값으로 메우지 않는다)
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import schema  # noqa: E402

BRAND_TOP = 0.06        # 화면 높이 대비 — 이 위에서 시작하는 좁은 띠는 고정 문구
BRAND_MAX_W = 0.40      # 화면 폭 대비
LOW_FONT = 0.5          # 글꼴 1위 점수 문턱(뜯기 unknown 과 같은 값)
SIDE_PAD = 40           # 가운데 정렬 글자 칸 = 화면 폭 − 양쪽 40px
TITLE_W_PAD = 20        # 제목 칸 = 원본 잉크 폭 + 양쪽 이만큼(가운데 정렬 기본 칸보다 넓을 때만)
LINE_SCALE_MIN = 0.03   # 제목 줄 크기가 평균에서 이만큼 넘게 벗어나면 줄 배율(line_scale)
ALIGN_CENTER = 20       # 자막 가운데들의 중앙값이 화면 가운데 ±이 안이면 가운데 정렬
ALIGN_EDGE = 12         # 왼쪽/오른쪽 끝이 이만큼 안으로 모이면 그 끝 정렬(가운데는 ALIGN_SPREAD 넘게 흩어졌을 때)
ALIGN_SPREAD = 40
CAP_W_MIN = 400         # 자간·낱말 간격을 역산할 자막의 최소 잰 폭(짧은 자막은 잰 폭 오차가 자간을 크게 흔든다)
CAP_W_SPREAD = 0.15     # 잰 폭/그린 폭 비의 사분위 폭(중앙값 대비) — 넘으면 잰 폭이 글 길이를 안 따른다(못 믿음)
LINE_RGB_DIFF = 40      # 제목 줄끼리 채움색이 이 값(채널 최대차)보다 다르면 줄마다 색(line_rgb)
FRAMED_TOL = 30         # 틀 있음 판정: 띠 사이 빈 줄이 바탕색 ±30 안


@lru_cache(maxsize=1)
def font_faces() -> dict:
    """장면꾸미기 화면의 @font-face: 글꼴 이름 → 파일 경로(첫 등록). 렌더러가 실제로 쓰는 파일."""
    html = (ROOT / "out/scene-style-ui-showcase.html").read_text(encoding="utf-8")
    out = {}
    for fam, url in re.findall(r'@font-face\s*\{[^}]*?font-family:\s*"?([A-Za-z0-9_-]+)"?;\s*src:\s*url\("([^"]+)"', html):
        out.setdefault(fam, (ROOT / "out" / url).resolve())
    return out


def family_of(font_file: str) -> str | None:
    """뜯기 글꼴 파일 이름(예 NotoSansKR-Bold.otf) → 등록 글꼴 이름. 파일 줄기(stem)가 같은 것만(추측 매핑 없음)."""
    stem = Path(font_file).stem.lower()
    for fam, path in font_faces().items():
        if path.stem.lower() == stem:
            return fam
    return None


def pick_font(fonts: dict | None) -> tuple[str | None, dict]:
    """뜯기 fonts → (등록 글꼴 이름, 기록). 순서 = 합산 top3 → 크롭별 top5 평균(없는 크롭은 0)."""
    note = {"top1": None, "top1_score": None, "picked_from": None, "font_confidence": None, "skipped": []}
    if not fonts or not fonts.get("ok"):
        note["why"] = (fonts or {}).get("failed", "뜯기에 글꼴 결과 없음")
        return None, note
    order = [(x["font"], x["score"]) for x in fonts.get("top3") or []]
    crops = fonts.get("per_crop") or []
    tot = {}
    for c in crops:
        for x in c.get("top5") or []:
            tot[x["font"]] = tot.get(x["font"], 0) + x["score"]
    order += sorted(((f, round(s / max(1, len(crops)), 4)) for f, s in tot.items()), key=lambda r: -r[1])
    if order:
        note["top1"], note["top1_score"] = order[0]
        note["font_confidence"] = "low" if order[0][1] < LOW_FONT else "ok"
    seen = set()
    for f, s in order:
        if f in seen:
            continue
        seen.add(f)
        fam = family_of(f)
        if fam:
            note["picked_from"] = {"file": f, "score": s}
            return fam, note
        note["skipped"].append(f"{f}(장면꾸미기 미등록)")
    note["why"] = "순위 안에 장면꾸미기 등록 글꼴이 없음"
    return None, note


def _pil_font(fam: str, size: float):
    return _pil_font_px(fam, max(1, int(round(size))))


@lru_cache(maxsize=256)
def _pil_font_px(fam: str, px: int):
    """woff2 는 열 때마다 압축을 풀어 느리다(시험 52초 실측) — 글꼴·크기별로 한 번만 연다."""
    from PIL import ImageFont
    return ImageFont.truetype(str(font_faces()[fam]), px)


def size_and_top(fam: str, text: str | None, ink_top: float, ink_h: float, line_h: float | None) -> dict:
    """잉크 높이·위 끝 → (글자 크기, 줄 칸 y, line_h). 렌더러는 줄 칸 높이 line_h 안에 글자 줄을 세로 가운데로 둔다
    (CSS line-height = line_h, 글꼴 ascent+descent 상자가 가운데) — 그 규칙을 그 글꼴의 실제 모양으로 거꾸로 푼다."""
    sample = (text or "").strip() or "가나다라마바사"
    f100 = _pil_font(fam, 100)
    b = f100.getbbox(sample, anchor="ls")           # 기준선 기준 잉크 상자(위는 음수)
    size = ink_h * 100 / max(1, b[3] - b[1])
    f = _pil_font(fam, size)
    asc, desc = f.getmetrics()
    bt = f.getbbox(sample, anchor="ls")[1]
    lh = line_h if line_h is not None else round(size * 1.15)
    y = ink_top - ((lh - (asc + desc)) / 2 + asc + bt)
    return {"size": round(size, 1), "y": round(y), "line_h": round(lh)}


def spacing_for(fam: str, size: float, text, target_w):
    """잰 잉크 폭에 맞추는 자간(px) — 그 글꼴·크기로 같은 글을 그린 잉크 폭과의 차를 글자 사이 수로 나눈다.
    글이나 폭을 모르면 None(자간 0 = 글꼴 그대로). 글꼴이 원본과 다를 때 폭이라도 맞추는 보정이라 크기의 -15%~+30% 안으로 묶는다."""
    if not text or not target_w or len(text) < 2:
        return None
    b = _pil_font(fam, size).getbbox(text, anchor="ls")
    ls = (target_w - (b[2] - b[0])) / (len(text) - 1)
    return round(max(-0.15 * size, min(0.3 * size, ls)), 1)


_INK_X: dict = {}


def _ink_x(font, ch: str):
    """글자 하나의 실제 잉크 가로 범위(advance 원점 기준) — getbbox 는 이 글꼴(Spoqa)에서 advance 상자(0~61)를 돌려
    글자 옆 여백 3~5px 를 못 봤다(10-16 실측: 모형 틈 0.2px vs 렌더 9px). 그려서 잰다."""
    key = (id(font), ch)
    if key not in _INK_X:
        from PIL import Image, ImageDraw
        sz = int(font.size * 3)
        im = Image.new("L", (sz, sz), 0)
        ImageDraw.Draw(im).text((font.size, font.size * 2), ch, font=font, fill=255, anchor="ls")
        xs = np.where(np.asarray(im).max(axis=0) > 128)[0]
        _INK_X[key] = (float(xs[0] - font.size), float(xs[-1] + 1 - font.size)) if len(xs) else None
    return _INK_X[key]


def _css_line(font, text: str, ls: float, ws: float) -> tuple[float, list[float]]:
    """CSS 처럼 한 줄을 놓는다 — 글자마다 advance + letter-spacing, 공백엔 word-spacing 을 더한다(렌더러 precision20-ui.js 의 spec-text).
    반환 (잉크 폭, 낱말 사이 잉크 틈 목록). 10-16 실측: 렌더 틈과 1~2px 안(모형 11.2/9.2/7.2 vs 렌더 11/9/8)."""
    x, boxes = 0.0, []
    for ch in text:
        bb = _ink_x(font, ch) if ch != " " else None
        boxes.append((ch, x + bb[0], x + bb[1]) if bb else (ch, None, None))
        x += font.getlength(ch) + ls + (ws if ch == " " else 0)
    ink = [(l, r) for ch, l, r in boxes if l is not None]
    gaps, k = [], 0
    while k < len(text):
        if text[k] == " ":
            j = k
            while j < len(text) and text[j] == " ":
                j += 1
            left = next((boxes[i][2] for i in range(k - 1, -1, -1) if boxes[i][2] is not None), None)
            right = next((boxes[i][1] for i in range(j, len(text)) if boxes[i][1] is not None), None)
            if left is not None and right is not None:
                gaps.append(right - left)
            k = j
        else:
            k += 1
    return (ink[-1][1] - ink[0][0]) if ink else 0.0, gaps


GAP_Q = 0.25   # 낱말 틈은 아래쪽 4분위로 맞춘다 — 받침·모음 모양 따라 우리 글꼴 틈이 5~13px 로 출렁여, 중앙값으로 맞추면 좁은 틈(5px)이 여전히 붙어 보인다


def _q(v: list, q: float = GAP_Q) -> float:
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def spacing_and_word_gap(fam: str, size: float, text, target_w, target_gap, gap_texts: list | None = None):
    """자간 + 낱말 간격(px) — 판단 주인 한 곳. 자간은 글자 사이 폭을, 낱말 간격은 **원본 낱말 사이 잉크 틈**(target_gap)을 맞춘다.
    ★10-16 사장님 반려: spacing_for 는 폭 차를 공백까지 포함한 글자 사이 수로 나눠 −7.4px 자간이 공백에도 걸렸다
      → 원본 낱말 틈 13~16px 가 우리 8~11px 로 줄어 '유리문에원판대자마자…'처럼 뭉개 보였다.
    target_gap = 원본 낱말 틈의 아래 4분위(caption_word_gap). gap_texts(원본 자막 글 전부)로 우리 틈의 아래 4분위를 잰다.
    자간(ls)은 spacing_for 그대로 둔다 — 낱말 간격을 넣고 폭을 다시 맞추면 자간이 −9.6px 로 더 줄어 글자끼리 붙었다(10-16 2판 실측:
      '대자마자' 획이 닿음). 글자 사이 틈은 −7.4 에서 이미 원본과 같다(픽셀 잰 글자 사이 틈 중앙 우리 3.5 / 원본 4px).
      그래서 원본 글 폭은 공백 수 × ws 만큼 넓어진다(감수 — 글자 붙음보다 낫다).
    반환 (ls, ws) — 글·폭·틈 중 하나라도 없으면 (spacing_for, 0)."""
    ls = spacing_for(fam, size, text, target_w)
    if ls is None or not target_gap or " " not in str(text).strip():
        return ls, 0
    font = _pil_font(fam, size)
    texts = [t for t in (gap_texts or [text]) if t and " " in t.strip()]
    gaps = [g for t in texts for g in _css_line(font, t, ls, 0.0)[1]]
    ws = target_gap - _q(gaps) if gaps else 0.0
    return ls, round(max(-0.5 * size, min(size, ws)), 1)


def caption_word_gap(src: str, J: dict, W: int, H: int, pol: str) -> float | None:
    """원본 자막의 낱말 사이 잉크 틈(px, 아래 4분위 GAP_Q) — 자막마다 구간 가운데 프레임의 자막 줄을 잘라 잉크 열 틈 중 큰 것 공백 수만큼.
    (ZdeZ 실측 10-16: 원본 12~16px, 글자 사이 4~7px)"""
    from shopping_shorts.channelkit.bench import probe
    cap = J.get("captions") or {}
    lh = st.median(g["line_h"] for g in cap.get("glyph") or [{"line_h": 60}])
    out = []
    for it, (a, b) in zip(cap.get("items") or [], cap.get("spans") or []):
        txt = " ".join(it.get("text") or [])
        k = txt.strip().count(" ")
        if not k or it.get("top_y") is None or int(it.get("lines") or 1) != 1:
            continue
        img = probe.grab(src, (a + b) / 2, f"scale={W}:{H}", W, H)
        if img is None:
            continue
        y0 = max(0, int(it["top_y"]) - 4); y1 = min(H, int(it["top_y"] + lh) + 4)
        g = img[y0:y1].astype(int).mean(axis=2)
        col = ((g < 100) if pol == "dark" else (g > 180)).any(axis=0)
        xs = np.where(col)[0]
        if len(xs) < 2:
            continue
        d = np.diff(xs) - 1
        big = sorted((int(v) for v in d if v > 0), reverse=True)[:k]
        if len(big) == k:
            out.extend(big)
    return float(_q(out)) if out else None


CAP_COL_PAD = 20         # 자막 글자 열 범위 양옆 여유(px) — 외곽선 고리가 들어갈 자리
OUTLINE_BG_TOL = 45      # 외곽선 바깥이 외곽선 색과 이 안이면 바탕(외곽선 아님)
OUTLINE_MAX = 16        # 외곽선 두께 상한(px) — 여기까지 끝을 못 찾으면 외곽선 아님(OE11 자막 검정 12px 은 13px 에서 끝난다)
OUTLINE_SHARE = 0.7     # 외곽선 고리: 이 비율 이상이 외곽선 색
EXT_MAX = 0.6           # 창 안으로 이어 잴 최대 길이 = 띠 높이 × 이 값
EXT_MIN_PX = 20         # 이어 잴 줄: 글자 채움색 점이 이 수 이상


def title_line_bottom(img, band, win) -> int:
    """제목 한 줄 잉크의 진짜 아래 끝 — 띠가 창 위 끝에서 끝나도 글자가 창(영상) 위로 이어져 그려졌으면 그 아래까지.
    채움색 = 띠 안에서 바탕(띠 바로 위 줄들)과 80 넘게 다른 점의 가운데값. 창 위 끝부터 아래로, 그 색 점이 EXT_MIN_PX 이상인
    줄이 이어지는 데까지(줄 사이 빈 줄 6개까지 허용 — 글자 외곽선·창 경계선). 끝나지 않았으면 band[1]."""
    if img is None or not win or band[1] < win[1] - 2:
        return band[1]
    a = img.astype(int)
    H = a.shape[0]
    core = a[band[0]:band[1]].reshape(-1, 3)
    bgc = np.median(a[max(0, band[0] - 8):band[0]].reshape(-1, 3), axis=0) if band[0] >= 8 else np.median(core, axis=0)
    far = core[np.abs(core - bgc).max(axis=1) > 80]
    if len(far) < 50:
        return band[1]
    fill = np.median(far, axis=0)
    # 이어지는 획만 — 띠 마지막 줄들에서 채움색이던 열(±3px) 안의 점만 센다(영상 속 비슷한 색은 빼려고. 1_V 분홍 2줄이 영상 속
    #   분홍을 글자로 이어 재 2줄이 1줄보다 커졌다)
    edge = (np.abs(a[max(0, band[1] - 4):band[1]] - fill).max(axis=2) < 50).any(axis=0)
    cols = np.convolve(edge.astype(int), np.ones(7, int), mode="same") > 0
    if cols.sum() < EXT_MIN_PX:
        return band[1]
    last, gap = band[1], 0
    for y in range(band[1], min(H, int(band[1] + EXT_MAX * (band[1] - band[0])))):
        hit = (np.abs(a[y] - fill).max(axis=1) < 50) & cols
        if int(hit.sum()) >= max(EXT_MIN_PX, 0.4 * int(edge.sum())):
            last, gap = y, 0
        else:
            gap += 1
            if gap > 6:
                break
    return last


def line_outline_of(img: np.ndarray, fill, over_from: int, bg=None) -> list | None:
    """한 줄 글자의 외곽선 [px, r, g, b] — 채움색 둘레를 한 겹씩 넓혀 가며, **창 영상 위 행**(over_from 행부터)에 걸린 고리만 본다.
    바탕과 같은 색 외곽선(흰 바탕의 흰 외곽선)은 바탕 위에선 안 보이고 창 위로 걸칠 때만 보인다(1_V 둘째 줄 실측) —
    analyze.text_fx_one 은 바탕 고리까지 섞어 12px 분홍처럼 틀린 값을 냈다. 색으로 '바탕 아님'을 고르면 흰 외곽선이 바탕(252)과
    같아 빠지므로 자리(행)로 고른다. 고리 색이 채움과 60 넘게 다르고 서로 40 안이면 외곽선. 창에 안 닿는 줄은 None(못 잼)."""
    import cv2
    a = img.astype(int)
    fm = (np.abs(a - np.array(fill)).max(axis=2) < 60).astype(np.uint8)
    # 영상 속 낱개 같은 색 점은 글자가 아니다 — 3×3 열림으로 지운다(그 둘레 고리가 외곽선 색을 흐렸다)
    fm = cv2.morphologyEx(fm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    if fm.sum() < 50:
        return None
    if bg is not None:   # 창 영상이 실제로 시작하는 행 — 창 다수결(1_V 352)보다 위로 비스듬히 들어올 수 있다(실측 324)
        far = ~cv2.dilate(fm, np.ones((31, 31), np.uint8)).astype(bool)       # 글자에서 15px 넘게 떨어진 점만
        vid = (np.abs(a - np.array(bg)).max(axis=2) > 30) & far
        rows = np.where(vid.sum(axis=1) > 0.3 * far.sum(axis=1).clip(1))[0]
        if len(rows):
            over_from = min(over_from, int(rows.min()))
    if over_from >= img.shape[0]:
        return None
    notbg = np.zeros(fm.shape, bool)
    notbg[max(0, over_from):] = True
    prev, color, px = fm.astype(bool), None, 0
    for r in range(1, OUTLINE_MAX + 1):
        d = cv2.dilate(fm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))).astype(bool)
        ring, prev = d & ~prev & notbg, d
        if ring.sum() < 30:
            if color is None and r <= 3:   # 글자 아래 끝이 창 위 행에 막 닿는 경우 — 처음 몇 겹은 창 행에 거의 없다
                continue
            break
        c = np.median(a[ring], axis=0)
        if r == 1:            # 첫 고리는 채움과 외곽선이 섞이는 경계(안티에일리어싱) — 색 판정 없이 두께에만 센다
            px = 1; continue
        if np.abs(c - np.array(fill)).max() <= 60 or (color is not None and np.abs(c - color).max() > 40):
            break
        # 고리의 대부분(OUTLINE_SHARE)이 외곽선 색이어야 — 어두운 영상 위 검정 외곽선은 고리 가운데값이 영상까지 검정이라
        #   두께가 12px 로 부풀었다(mY 노란 2줄, 실제 2~3px, 10-16). 영상은 색이 흩어져 비율이 먼저 떨어진다
        ref = c if color is None else color
        if r > 2 and float((np.abs(a[ring] - ref).max(axis=1) <= 40).mean()) < OUTLINE_SHARE:
            break
        color = c if color is None else color
        px = r
    if color is not None:
        # 외곽선 바깥(글자에서 OUTLINE_MAX+4~+8px)의 색이 외곽선 색과 같으면 외곽선이 아니라 그 바탕이다
        #   (mY: 고리 2~13px 이 (46,29,38) — 그 바깥 어두운 공연장 영상과 같은 색. OE11 자막 검정 0 은 바깥 영상(빨강·회색)과 다르다)
        dd = lambda r: cv2.dilate(fm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))).astype(bool)   # noqa: E731
        outer = dd(OUTLINE_MAX + 8) & ~dd(OUTLINE_MAX + 4) & notbg
        if outer.sum() > 50 and float((np.abs(a[outer] - color).max(axis=1) <= OUTLINE_BG_TOL).mean()) > 0.6:
            return None
    if px >= OUTLINE_MAX:
        # 12px 까지 고리 색이 안 바뀌었다 = 외곽선 끝을 못 찾음 — 외곽선이 아니라 같은 색 바탕·영상(mY: 검정 띠·어두운 공연장 영상 위
        #   노란 글자, 고리 3~13px 이 전부 (46,29,38)). 못 잰 값으로 12px 를 내지 않는다
        return None
    return [px, *[int(v) for v in color]] if color is not None and px >= 2 else None


def caption_cols(img: np.ndarray, fill, ink_h: float) -> tuple[int, int] | None:
    """자막 줄 띠(img) 안 자막 글자의 열 범위 — 채움색 덩어리 중 띠 위아래에 안 닿고(영상 속 큰 흰 면 제외) 높이가 줄 높이의
    0.15~1.3배·폭 ≤ 1.5배인 것(글자·낱자)을 왼→오 로 이어(틈 ≤ 0.8×줄 높이) 가장 넓은 무리. 2개 미만이면 None.
    mY 1초: 흰 얼음 덩어리를 빼 23~721 → 355~721('선수가 퍽을')."""
    import cv2
    fm = (np.abs(img.astype(int) - np.array(fill)).max(axis=2) < 60).astype(np.uint8)
    n, _, S, _ = cv2.connectedComponentsWithStats(fm, 8)
    H = img.shape[0]
    xs = sorted((int(x), int(x + w)) for x, y, w, h, a in (S[i] for i in range(1, n))
                if y > 0 and y + h < H and 0.15 * ink_h <= h <= 1.3 * ink_h and w <= 1.5 * ink_h and a >= 20)
    if len(xs) < 2:
        return None
    groups = [[xs[0]]]
    for a, b in xs[1:]:
        if a - max(e for _, e in groups[-1]) <= 0.8 * ink_h:
            groups[-1].append((a, b))
        else:
            groups.append([(a, b)])
    g = max(groups, key=lambda g: sum(e - s0 for s0, e in g))
    return (min(a for a, _ in g), max(b for _, b in g)) if len(g) >= 2 else None


def band_rows_end(b, win) -> int:
    """띠 가로 범위를 잴 마지막 행. 창에 붙은 띠(끝이 창 시작 ±8px)는 위 70% 행만 — 창 영상이 띠 아래쪽으로 비스듬히
    들어와(1_V 실측: 창 다수결 352인데 324행부터 영상 가장자리) 왼쪽 끝이 0으로 잡혔다."""
    if win and b[1] >= win[1] - 8:
        return int(b[0] + 0.7 * (b[1] - b[0]))
    return b[1]


def ink_columns(img: np.ndarray, y0: int, y1: int, bg: list, tol: int = 40) -> tuple[int, int] | None:
    """띠 [y0,y1] 안에서 바탕과 다른 점이 있는 가로 범위."""
    band = img[max(0, y0):y1 + 1].astype(int)
    diff = np.abs(band - np.array(bg)).max(axis=2) > tol
    cols = np.where(diff.sum(axis=0) > 1)[0]
    return (int(cols.min()), int(cols.max())) if len(cols) else None


BRAND_CORE_RATIO = 0.6   # 진한 글자 몸 높이가 가장 큰 띠의 이 비율보다 작고 좁으면 고정 문구
CORE_DIFF = 150          # 진한 글자 몸 = 바탕과 이만큼 넘게 다른 점
GLOW_DIFF = 25           # 번짐 = 바탕과 25~150 다른 점
GLOW_MIN_PX = 10         # 번짐이 글자에서 이만큼 넘게 퍼져야 글로우
GLOW_SHARE = 2.0         # 번짐 점이 진한 점의 이 배 넘으면 글로우


def band_core(img, b, bg) -> dict | None:
    """띠의 진한 글자 몸(바탕과 CORE_DIFF 넘게 다른 점) 상자·높이·채움색."""
    c = img[b[0]:b[1] + 1].astype(int)
    m = np.abs(c - np.array(bg)).max(axis=2) > CORE_DIFF
    rows, cols = np.where(m.sum(axis=1) >= 3)[0], np.where(m.sum(axis=0) >= 1)[0]
    if not len(rows) or not len(cols):
        return None
    return {"y0": b[0] + int(rows.min()), "y1": b[0] + int(rows.max()), "x0": int(cols.min()), "x1": int(cols.max()),
            "h": int(rows.max() - rows.min() + 1), "w": int(cols.max() - cols.min() + 1), "fill": [int(v) for v in np.median(c[m], axis=0)],
            "n": int(m.sum())}


def glow_of(img, b, bg, core) -> dict | None:
    """글로우(글자 둘레 번짐 빛) — 띠 안 '바탕과 조금 다른 점'(GLOW_DIFF~CORE_DIFF)이 진한 점의 GLOW_SHARE 배 넘으면.
    색 = 그 점 중 밝은 10% 의 가운데값, 두께 = 글자 몸에서 번짐 점까지 거리의 90 분위."""
    import cv2
    if img is None or not core:
        return None
    c = img[b[0]:b[1] + 1].astype(int)
    d = np.abs(c - np.array(bg)).max(axis=2)
    strong, soft = d > CORE_DIFF, (d > GLOW_DIFF) & (d <= CORE_DIFF)
    if soft.sum() < GLOW_SHARE * max(1, strong.sum()):
        return None
    dist = cv2.distanceTransform((~strong).astype(np.uint8), cv2.DIST_L2, 5)
    lum = c.max(axis=2)
    bright = soft & (lum >= np.percentile(lum[soft], 90))
    px = int(round(float(np.percentile(dist[soft], 90))))
    if px < GLOW_MIN_PX:      # 글자에 붙은 외곽선·안티에일리어싱(ZdeZ [광고] 회색 외곽선 4px)은 글로우가 아니다
        return None
    return {"px": px, "rgb": [int(v) for v in np.median(c[bright], axis=0)]}


def two_tone(img: np.ndarray, box, bg: list) -> dict:
    """작은 고정 문구(예 회색 채움+짙은 외곽선)의 채움·외곽선 — 바탕과 다른 점을 밝기로 둘로 나눠 많은 쪽 안=채움."""
    import cv2
    x0, y0, x1, y1 = box
    crop = img[y0:y1 + 1, x0:x1 + 1].astype(int)
    m = np.abs(crop - np.array(bg)).max(axis=2) > 40
    if m.sum() < 30:
        return {"fill": None, "outline": None}
    lum = crop[..., 0] * .299 + crop[..., 1] * .587 + crop[..., 2] * .114
    cut = (lum[m].min() + lum[m].max()) / 2
    dark, light = m & (lum < cut), m & (lum >= cut)
    if light.sum() < 0.15 * m.sum():          # 한 색 글자
        return {"fill": [int(v) for v in np.median(crop[m], axis=0)], "outline": None}
    dist = cv2.distanceTransform(dark.astype(np.uint8), cv2.DIST_L2, 3)
    px = max(1, int(round(2 * np.percentile(dist[dark], 90))))   # 고리 두께 T 면 고리 안 가장자리까지 거리의 최대 ≈ T/2
    return {"fill": [int(v) for v in np.median(crop[light], axis=0)],
            "outline": {"px": px, "rgb": [int(v) for v in np.median(crop[dark], axis=0)]}}


def framed(img: np.ndarray, rows: list[tuple[int, int]], bg: list) -> bool:
    """이 프레임에 틀(바탕색)이 있나 — 창 위 띠 사이 빈 줄들이 바탕색이면 틀이 있다."""
    pts = np.concatenate([img[a:b].reshape(-1, 3) for a, b in rows if b > a]).astype(int)
    # 허용 30: 뜯기 bg_rgb 는 여러 프레임 중앙값이라 한 프레임 바탕과 15 안팎 다르다(ZdeZ 실측 241,235,237 vs 251,248,252)
    return bool(len(pts)) and float((np.abs(pts - np.array(bg)).max(axis=1) < FRAMED_TOL).mean()) > 0.85


def paint_bg(img, window, bands, bg) -> list | None:
    """틀 바탕의 실제 칠 = 창 위 띠 사이 빈 줄들의 중앙값. 뜯기 bg 와 30 넘게 다르면(빈 줄에 다른 것이 있음) None."""
    rows = gap_rows(window, [tuple(b) for b in bands])
    if not rows:
        return None
    pts = np.concatenate([img[a:b].reshape(-1, 3) for a, b in rows if b > a])
    med = [int(v) for v in np.median(pts, axis=0)]
    return med if max(abs(m - g) for m, g in zip(med, bg)) <= FRAMED_TOL else None


def gap_rows(window, bands) -> list[tuple[int, int]]:
    ys = sorted(bands)
    edges, prev = [], 0
    for a, b in ys:
        if a - prev > 8:
            edges.append((prev + 2, a - 2))
        prev = b
    if window and window[1] - prev > 8:
        edges.append((prev + 2, window[1] - 2))
    return edges


OBLIQUE_DEG = 14.0      # 크롬 합성 기울임(font-synthesis:style) 각 — 렌더 실측으로 맞춘 값(보고 참조)
ITALIC_MIN = 6.0        # 글자 기둥이 이 각도(도) 이상 오른쪽으로 누우면 기울임 — 렌더러 합성 기울임은 약 11~14도


def slant_deg(mask: np.ndarray) -> float:
    """글자 잉크 마스크의 기울기(도, + = 위가 오른쪽). 각도마다 위아래를 반대로 밀어(전단) 세로 기둥이 가장 곧게 서는
    각 = 열 투영 제곱합이 가장 큰 각. 분석기 값이 없을 때 프레임에서 직접 잰다."""
    import cv2
    m = mask.astype(np.float32)
    h, w = m.shape
    yc = h / 2
    best, ang = -1.0, 0.0
    for a in np.arange(-25, 25.5, 1.0):
        t = np.tan(np.radians(a))
        M = np.float32([[1, t, -t * yc], [0, 1, 0]])
        col = cv2.warpAffine(m, M, (w, h)).sum(axis=0)
        sc = float((col ** 2).sum())
        if sc > best:
            best, ang = sc, float(a)
    return ang


def italic_of(img, bands_cols, bg, notes: list, label: str) -> bool:
    """띠들의 글자 기울기 → 기울임 여부. 프레임이 없으면 False + notes."""
    if img is None or not bg:
        notes.append(f"{label} 기울임: 프레임 없음 → false(안 잼)")
        return False
    angs = []
    for b, cols in bands_cols:
        if not cols:
            continue
        crop = img[b[0]:b[1] + 1, cols[0]:cols[1] + 1].astype(int)
        mask = np.abs(crop - np.array(bg)).max(axis=2) > 40
        if mask.sum() > 50:
            angs.append(slant_deg(mask))
    if not angs:
        notes.append(f"{label} 기울임: 잉크 없음 → false"); return False
    a = st.median(angs)
    notes.append(f"{label} 기울기 {a:+.0f}도(기둥 전단 투영) → {'기울임' if a >= ITALIC_MIN else '바름'}")
    return a >= ITALIC_MIN


def title_font(J: dict, img, title_b, texts: list, pol: str, bg=None) -> tuple[str | None, str]:
    """제목 글꼴 — ① 분석기 fonts.title(2판) ② 없으면 분석기와 같은 판별 함수(fontmatch.rank)를 제목 줄에 직접 돌린다
    (판별 주인은 fontmatch 그대로 — 여기선 부르기만) ③ 그것도 못 하면 None(부르는 쪽이 자막 글꼴 + notes)."""
    ft = (J.get("fonts") or {}).get("title")
    if isinstance(ft, dict) and (ft.get("ok") or ft.get("top3")):   # 분석기 2판 fonts.title = {top3, top5, n_bands, slant_deg, italic}('ok' 없음)
        fam, note = pick_font({"ok": True, "top3": ft.get("top3") or [], "per_crop": [{"top5": ft.get("top5") or []}]})
        return fam, f"분석기 fonts.title 1위 {note.get('top1')}({note.get('top1_score')}), 신뢰 {note.get('font_confidence')}"
    if img is None or not texts:
        return None, "분석기 fonts.title 없음 · 프레임/제목 OCR 없어 직접 판별 못 함"
    from tools.calcopy.engine import fontmatch
    y0, y1 = title_b[0][0][0] - 12, title_b[-1][0][1] + 12
    masks = fontmatch.line_masks(img[max(0, y0):y1], pol)
    if len(masks) != len(texts) and bg is not None and len(title_b) == len(texts):
        # 극성 문턱으로 못 가른 줄(검정 바탕 빨강 줄)은 띠마다 진한 글자 몸(바탕과 CORE_DIFF 넘게 다른 점)으로 — OE11 2줄
        masks = [np.abs(img[max(0, b[0] - 2):b[1] + 3].astype(int) - np.array(bg)).max(axis=2) > CORE_DIFF for b, _ in title_b]
    if len(masks) != len(texts):
        return None, f"분석기 fonts.title 없음 · 제목 잉크 줄 {len(masks)} ≠ OCR 줄 {len(texts)}"
    per, tot = [], {}
    for m, t in zip(masks, texts):
        r = fontmatch.rank(m, t)
        per.append({"text": t, "top5": [{"font": x["font"], "score": x["score"]} for x in r[:5]]})
        for x in r:
            tot.setdefault(x["font"], []).append(x["score"])
    top = sorted(({"font": k, "score": round(float(np.mean(v)), 4)} for k, v in tot.items()), key=lambda r: -r["score"])
    fam, note = pick_font({"ok": True, "top3": top[:3], "per_crop": per})
    return fam, (f"분석기 fonts.title 없음 → fontmatch.rank 를 제목 {len(texts)}줄에 직접(1위 {note.get('top1')} "
                 f"{note.get('top1_score')}, 신뢰 {note.get('font_confidence')})")


def band_font(img, b, cols, text: str, bg) -> tuple[str | None, str]:
    """고정 문구 띠의 글꼴 — 분석기는 이 띠를 판별하지 않는다. 바탕과 다른 점 전체(채움+외곽선)를 글자 모양으로 보고
    fontmatch.rank(분석기와 같은 판별 함수)를 직접 부른다. 외곽선만큼 획이 두껍게 보여 굵은 쪽으로 기울 수 있다."""
    if img is None or not cols or not text:
        return None, "프레임/글자 없어 판별 못 함 → 자막 글꼴"
    from tools.calcopy.engine import fontmatch
    crop = img[b[0]:b[1] + 1, cols[0]:cols[1] + 1].astype(int)
    mask = np.abs(crop - np.array(bg)).max(axis=2) > 40
    r = fontmatch.rank(mask, text)
    fams, seen = [], set()
    for x in r:
        f = family_of(x["font"])
        if f and f not in seen:
            seen.add(f); fams.append((f, x["score"]))
    if not fams:
        return None, "fontmatch 순위에 등록 글꼴 없음 → 자막 글꼴"
    return fams, f"fontmatch.rank 직접(채움+외곽선 모양, 1위 {r[0]['font']} {r[0]['score']})"


def band_body(b, cols, o: int, ital: bool) -> tuple[int, int, int]:
    """잰 띠·가로 범위(채움+외곽선 전체)에서 '글자 몸'의 높이·폭과 기울임이 윗끝을 미는 양.
    렌더러는 외곽선을 글자 밖에 더 그리고(paint-order stroke) 기울임은 윗부분을 OBLIQUE_DEG 만큼 민다 — 그 둘을 뺀다.
    (2026-10-16 대조: 빼지 않아 [광고] 글자 높이 61 vs 원본 52~55, 오른쪽 끝이 화면 끝 1079에 닿았다)"""
    body_h = (b[1] - b[0] + 1) - 2 * o
    lean = round(np.tan(np.radians(OBLIQUE_DEG)) * body_h) if ital else 0
    return body_h, (cols[1] - cols[0] + 1) - 2 * o - lean, lean


def build(J: dict, frame_img: np.ndarray | None, ocr: dict | None, tail_probe=None, cap_word_gap: float | None = None,
          title_font_fixed: str | None = None) -> dict:
    """뜯기 → 설명서(검사 전 원본 모양 + notes). frame_img = 틀이 있는 구간의 원본 한 프레임(RGB),
    ocr = {"title": [줄...], "brand": "글"} 또는 None, tail_probe(t)→bool = 그 시각 틀이 있나(없으면 뜯기 값 그대로)."""
    notes = []
    pr = J.get("probe") or {}
    W, H = int(pr.get("w") or 1080), int(pr.get("h") or 1920)
    L = J.get("layout") or {}
    bg = L.get("bg_rgb")
    win = L.get("window")
    layers = []
    paint = paint_bg(frame_img, win, L.get("above_bands") or [], bg) if frame_img is not None and bg else None
    if paint:
        # 칠할 색은 프레임의 실제 바탕(띠 사이 빈 줄 중앙값). 뜯기 bg_rgb 는 bench 의 '잰 값'이라 실제 칠보다 어둡게 나온다
        #   (ZdeZ: 잰 값 241,235,237 / 실제 251,248,252). 잰 값을 칠하면 같은 자로 다시 잴 때 한 번 더 어두워진다(232,222,222 실측).
        notes.append(f"바탕색 = 프레임 실제 칠 {paint} (뜯기 잰 값 {bg})")
        layers.append({"kind": "bg", "rgb": paint})
    elif bg:
        layers.append({"kind": "bg", "rgb": [int(v) for v in bg]})
    else:
        notes.append("배경색 없음(뜯기 layout.bg_rgb) — bg 층 생략")
    if win:
        layers.append({"kind": "video", "x": win[0], "y": win[1], "w": win[2], "h": win[3], "radius": 0})
    fam, fnote = pick_font(J.get("fonts"))
    if not fam:
        notes.append(f"글꼴 못 정함: {fnote.get('why')} — 글자 층 생략")
    elif fnote.get("font_confidence") == "low":
        notes.append(f"글꼴 1위 {fnote['top1']}({fnote['top1_score']}) < {LOW_FONT} — 확신 낮음. 쓴 글꼴 {fam}({fnote['picked_from']})")
    pol = L.get("ink_polarity") or "dark"            # 자막 잉크 극성(뜯기 layout) — 자막 층에만
    # 창 위 띠(제목·고정 문구)의 극성은 바탕 밝기로 — bench bands.polarity 와 같은 규칙. 자막 극성을 빌려 쓰면
    #   창 안 흰 자막 편(ho5·w-Y)에서 검정 제목을 '밝은 글자'로 재 채움·글꼴·외곽선이 전부 틀렸다(2026-10-16 실측).
    from shopping_shorts.channelkit.bench.bands import polarity
    tpol = polarity(0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) if bg else pol

    # 창 위 고정 띠 → brand / title
    bands = [tuple(b) for b in (L.get("above_bands") or [])]
    brand_b, title_b = [], []
    cores = {tuple(b): band_core(frame_img, b, bg) if frame_img is not None and bg else None for b in bands}
    core_h = [c["h"] for c in cores.values() if c]
    for b in sorted(bands):
        cols = ink_columns(frame_img, b[0], band_rows_end(b, win), bg) if frame_img is not None and bg else None
        narrow = cols is not None and (cols[1] - cols[0]) < BRAND_MAX_W * W
        c = cores.get(tuple(b))
        # 화면 맨 위가 아니어도, 진한 글자 몸이 좁고 다른 띠 글자보다 많이 작으면 고정 문구(채널명) — 핫템 OE11: 초록 글로우 채널명
        #   (글로우로 띠가 126px 로 부풀어 제목 1줄로 들어가 제목이 3줄·한 색이 됐다, 10-16)
        small = bool(c and c["w"] < BRAND_MAX_W * W and len(core_h) > 1 and c["h"] < BRAND_CORE_RATIO * max(h for h in core_h if h != c["h"] or core_h.count(h) > 1))
        (brand_b if (b[0] < BRAND_TOP * H and narrow) or small else title_b).append((b, cols))
    if frame_img is None and bands:
        notes.append("원본 프레임 없음 — 띠 가로 범위를 못 재 모든 띠를 제목으로 봄")
    otext = ocr or {}
    title_ink_w = None
    if title_b and fam:
        tl = otext.get("title") or []
        tfam, tsrc = (title_font_fixed, "고정(--title-font: 하위 스타일에서 확정한 제목 글꼴)") if title_font_fixed else title_font(J, frame_img, title_b, tl, tpol, bg)
        if not title_font_fixed and "신뢰 low" in tsrc and frame_img is not None and tl:
            # 분석기 판별 신뢰가 낮으면 제목 줄만(고정 문구 띠를 뺀) 같은 판별 함수로 다시 재 점수가 높은 쪽 — 분석기는 채널명 띠까지
            #   한 묶음으로 재 명조(RIDIBatang 0.448)를 냈다(OE11, 정답 TmonMonsori, 10-16)
            d_fam, d_src = title_font({}, frame_img, title_b, tl, tpol, bg)
            a_sc = float(re.search(r"\(([0-9.]+)\)", tsrc).group(1)) if re.search(r"\(([0-9.]+)\)", tsrc) else 0
            d_m = re.search(r"1위 \S+ ([0-9.]+)", d_src)
            if d_fam and d_m and float(d_m.group(1)) > a_sc:
                notes.append(f"제목 글꼴: 분석기 {tfam}({a_sc}, 신뢰 low) 대신 제목 줄 직접 판별 {d_fam}({d_m.group(1)})")
                tfam, tsrc = d_fam, d_src
        if tfam:
            notes.append(f"제목 글꼴 {tfam} — {tsrc}")
        else:
            tfam = fam
            notes.append(f"제목 글꼴 = 자막 글꼴({fam}) — {tsrc}")
        fam_c, fam = fam, tfam            # 이 블록 안에서만 제목 글꼴(아래 자막·문구는 fam_c 로 되돌린다)
        lines = len(title_b)
        line_h = (title_b[-1][0][0] - title_b[0][0][0]) / (lines - 1) if lines > 1 else None
        fits = [size_and_top(fam, tl[i] if i < len(tl) else None, b[0], b[1] - b[0] + 1, line_h) for i, (b, _) in enumerate(title_b)]
        # 창 위 끝에 닿은 줄은 띠(창 위까지)로만 재면 잉크 아래가 잘린다 — 글자가 영상 위로 이어져 그려진 틀(mY: 노란 2줄이 창 위
        #   347 아래 366까지)은 그 아래까지 이어 잰다. 이어 재지 않으니 크기 138(정답 148)·자리 위로·제목 끝–창 간격 136px 이었다(10-16)
        ext = [title_line_bottom(frame_img, b, win) for b, _ in title_b]
        if any(e > b[1] for e, (b, _) in zip(ext, title_b)):
            fits = [size_and_top(fam, tl[i] if i < len(tl) else None, b[0], e - b[0] + 1, line_h) for i, (e, (b, _)) in enumerate(zip(ext, title_b))]
            notes.append(f"제목 줄 아래 끝을 창 안까지 이어 잼: {[(b[1], e) for e, (b, _) in zip(ext, title_b) if e > b[1]]}")
        size = round(st.mean(f["size"] for f in fits), 1)
        # 줄마다 크기가 다르면(LINE_SCALE_MIN 넘게) 줄 배율로 — 평균 하나로 그리면 1줄이 작고 얇게, 2줄이 크게 나왔다(10-16 LOO)
        line_scale = [round(f["size"] / size, 3) for f in fits] if max(abs(f["size"] / size - 1) for f in fits) > LINE_SCALE_MIN else None
        if line_scale:
            notes.append(f"제목 줄마다 크기 {[f['size'] for f in fits]} → size {size} × line_scale {line_scale}")
        ys = [f["y"] - i * fits[0]["line_h"] for i, f in enumerate(fits)]   # 줄마다 푼 첫 줄 위치의 평균
        cols = [c for _, c in title_b if c]
        title_ink_w = max(c[1] - c[0] + 1 for c in cols) if cols else None   # 프레임 실측 제목 가장 긴 줄 잉크 폭 → preset rules.fill_w(글꼴 계산보다 먼저)
        al = align_of(cols, W)
        if al["align"] == "center" and title_ink_w and title_ink_w + 2 * TITLE_W_PAD > al["w"]:
            # 글자 칸이 원본 잉크 폭보다 좁으면 렌더러가 칸에 맞춰 글자를 줄인다(10-16 1_V: 잉크 1032 > 칸 1000 → 1줄 높이 91→73)
            al["w"] = min(W, title_ink_w + 2 * TITLE_W_PAD)
            notes.append(f"제목 칸 폭 {al['w']} — 원본 가장 긴 줄 잉크 {title_ink_w}px 가 기본 칸보다 넓다")
        sp = [(c[1] - c[0], spacing_for(fam, fits[i]["size"] if line_scale else size, tl[i], c[1] - c[0] + 1))
              for i, (_, c) in enumerate(title_b) if i < len(tl) and c]
        # 자간은 줄별 값 중 가장 작은 것 하나 — 평균 내면 한 줄의 큰 자간이 다른 줄을 원본보다 넓혀 칸 밖으로 밀고 렌더러가 글자를 줄였다
        #   (10-16 1_V: 줄별 평균 15.9 → 1줄 높이 원본 90 vs 우리 79 / 7DY: 2줄 값 26.2 를 1줄에 쓰니 1줄 폭 866→949, 높이 110→101).
        #   가장 작은 값이면 어느 줄도 원본 폭을 넘지 않는다(남는 줄은 원본보다 조금 좁다)
        sp = [v for _, v in sp if v is not None]
        sp = [min(sp)] if sp else []
        fx, line_rgb, line_outline = None, None, None
        if frame_img is not None:
            from tools.calcopy.engine.analyze import text_fx_one
            y0, y1 = title_b[0][0][0] - 12, title_b[-1][0][1] + 12
            fx = text_fx_one(frame_img[max(0, y0):y1], tpol, bg)
            # 줄마다 채움색(예: 1줄 검정 + 2줄 자홍) — 두 줄을 한 번에 재면 중앙값이 한쪽 색이 된다(1_V 실측 [102,0,68])
            fills = [(text_fx_one(frame_img[max(0, bb[0] - 4):bb[1] + 5], tpol, bg) or {}).get("fill_rgb") for bb, _ in title_b]
            # 분석기 채움색이 못 잰 줄(검정 바탕의 빨강 — 밝기 극성 'bright' 문턱 아래, OE11 2줄)은 진한 글자 몸 가운데값으로
            fills = [f or (cores.get(tuple(bb)) or {}).get("fill") for f, (bb, _) in zip(fills, title_b)]
            if all(fills) and max(max(abs(p - q) for p, q in zip(f, fills[0])) for f in fills) > LINE_RGB_DIFF:
                line_rgb = fills
            lo = [line_outline_of(frame_img[max(0, bb[0] - 4):bb[1] + 16], f, (win[1] - max(0, bb[0] - 4)) if win else 10 ** 6, bg)
                  if f else None for (bb, _), f in zip(title_b, fills)]
            if any(lo):
                line_outline = lo
                notes.append(f"제목 줄별 외곽선 {lo} (창 위로 걸친 고리만 잼)")
        layers.append({"kind": "text", "role": "title", **al, "y": round(st.mean(ys)), "lines": lines,
                       "font": fam, "size": size, "line_h": fits[0]["line_h"],
                       "rgb": (line_rgb[0] if line_rgb else (fx or {}).get("fill_rgb")) or ([0, 0, 0] if tpol == "dark" else [255, 255, 255]),
                       "line_rgb": line_rgb, "line_scale": line_scale, "outline": None if line_outline else (fx or {}).get("outline"),
                       "line_outline": line_outline, "shadow": None,
                       "box": ({"rgb": fx["box"]["color"], "pad": 0, "radius": 0} if fx and fx.get("box") else None),
                       "italic": italic_of(frame_img, title_b, bg, notes, "제목"),
                       "letter_spacing": round(st.mean(sp), 1) if sp else 0, "enter": None,
                       "text": "\n".join(tl) if tl else None})
        if not tl:
            notes.append("제목 글자 OCR 없음 → text null(크기는 표본 글자로 잼)")
        if fx is None:
            notes.append("제목 채움색 못 잼 → 잉크 극성 기본색")
        fam = fam_c
    # 자막
    cap = J.get("captions") or {}
    items = [i for i in cap.get("items") or [] if i.get("top_y") is not None]
    fxs = (J.get("text_fx") or {}).get("summary") or {}
    if items and fam:
        top = st.median(i["top_y"] for i in items)
        ink_h = fxs.get("line_h_px") or st.median(g["line_h"] for g in cap.get("glyph") or [{"line_h": 0}])
        # 잰 줄 높이는 외곽선까지 든 잉크다 — 크기는 채움 글자로 역산하니 외곽선 두께×2 를 뺀다(렌더러 외곽선은 글자 밖으로 덧그린다).
        #   10-16 mY: line_h_px 80.5(외곽선 5px 포함)로 역산해 88.5 — 정답 63.7
        if fxs.get("outline_px"):
            notes.append(f"자막 잰 높이 {ink_h}px 에서 외곽선 {fxs['outline_px']}px×2 를 빼고 크기 역산")
            ink_h = ink_h - 2 * fxs["outline_px"]
        first = next((i["text"][0] for i in items if i.get("text")), None)
        fit = size_and_top(fam, first, top, ink_h, None)
        it0 = caption_width_ref(fam, fit["size"], items, notes)
        cap_ls, cap_ws = spacing_and_word_gap(fam, fit["size"], it0["text"][0], it0["widths"][0], cap_word_gap,
                                              [" ".join(i.get("text") or []) for i in items]) if it0 else (0, 0)
        if cap_ws:
            notes.append(f"자막 낱말 간격 {cap_ws}px — 원본 낱말 틈 {cap_word_gap}px 에 맞춤(자간 {cap_ls}px 은 글자 사이만)")
        # 자막 칸 줄 수 = 자막들의 최빈 줄 수(동률이면 큰 쪽) — 최댓값이면 잘못 센 몇 개(OE11: 같은 글이 1줄·2줄로 둘 다 나옴)가
        #   1줄 자막 틀을 2줄 칸으로 만들었다(10-16)
        import collections
        lc = collections.Counter(int(i.get("lines") or 1) for i in items)
        lines = max(lc, key=lambda k: (lc[k], k))
        if len(lc) > 1:
            notes.append(f"자막 줄 수 {dict(lc)} → 최빈 {lines}줄 칸")
        # 곡선 첫 칸은 글자가 아직 안 떠 bbox None 일 수 있다(팝 등장 첫 프레임 — 스타픽룸·잇템로그 ro1l) → 첫 실측 칸을 쓴다
        boxes = [b for c in (J.get("caption_motion") or {}).get("starts") or []
                 for b in [next((k.get("bbox") for k in c.get("curve") or [] if k.get("bbox")), None)] if b]
        al = align_of([(b[0], b[0] + b[2]) for b in boxes], W) if boxes else {"x": W // 2, "w": W - 2 * SIDE_PAD, "align": "center"}
        ol = fxs.get("outline_px")
        ol_rgb = fxs.get("outline_rgb")
        if frame_img is not None and fxs.get("fill_rgb"):
            # 자막 외곽선은 프레임의 자막 줄 · **자막 글자 열 범위 안**에서 직접 잰다 — 판단은 line_outline_of 한 곳(제목 줄과 같은 함수),
            #   열 범위는 caption_cols. 분석기 요약은 못 믿는다: OE11 요약 1px 회색(104) · 실측 검정 13px / mY 요약 3px 회색(110 = 안티
            #   에일리어싱 첫 고리 색) · 실측 검정 4px(전폭으로 재면 흰 얼음 영상이 섞여 [2,3,0,0]). 못 재면 분석기 값 그대로.
            #   크기 역산(위)은 분석기 줄 높이와 짝인 분석기 외곽선 값으로 한다 — OE11 줄 높이 75 = 채움 높이 실측 74(외곽선 미포함)
            y0 = int(max(0, top - 8)); y1 = int(min(frame_img.shape[0], top + ink_h + 20))
            cc = caption_cols(frame_img[y0:y1], fxs["fill_rgb"], ink_h)
            crop = frame_img[y0:y1, max(0, cc[0] - CAP_COL_PAD):cc[1] + CAP_COL_PAD] if cc else frame_img[y0:y1]
            m = line_outline_of(crop, fxs["fill_rgb"], 0, None)
            if m:
                notes.append(f"자막 외곽선 {m[0]}px {m[1:]} — 프레임 자막 줄 열 {cc or '전폭'} 에서 직접 잼(분석기 요약 {ol}px {ol_rgb})")
                ol, ol_rgb = m[0], m[1:]
        layers.append({"kind": "text", "role": "caption", **al, "y": fit["y"], "lines": lines, "font": fam,
                       "size": fit["size"], "line_h": fit["line_h"],
                       "rgb": fxs.get("fill_rgb") or ([0, 0, 0] if pol == "dark" else [255, 255, 255]), "line_rgb": None,
                       "outline": {"px": ol, "rgb": ol_rgb} if ol and ol_rgb else None,
                       "shadow": None, "box": ({"rgb": fxs["box"]["color"], "pad": 0, "radius": 0} if fxs.get("box") else None),
                       "italic": False, "letter_spacing": cap_ls if cap_ls is not None else 0, "word_spacing": cap_ws or 0,
                       "enter": caption_enter_of(J, notes), "emphasis": None})
        notes.append("자막 낱말 강조: 뜯기에 강조 낱말·색 항목이 없다(text_fx 는 자막 전체 채움색만) — 분석기에 넘길 목록")
        if fxs.get("shadow"):
            notes.append(f"자막 그림자 {fxs['shadow']} — 뜯기 값 모양을 설명서 그림자로 옮기는 규칙 없음(미반영)")
        if not fxs:
            notes.append("자막 글자 효과 요약 없음 → 잉크 극성 기본색")
    # 고정 문구
    for b, cols in brand_b:
        txt = otext.get("brand")
        if not txt:
            notes.append(f"띠 {b} 는 고정 문구로 보이나 글자 OCR 없음 → 층 생략(brand 는 글이 있어야 그린다)")
            continue
        core = cores.get(tuple(b))
        glow = glow_of(frame_img, b, bg, core)
        if glow:   # 글로우 띠: 크기·자리·글꼴은 진한 글자 몸만으로(번짐은 잉크가 아니다), 채움 = 진한 점 가운데값
            b, cols = (core["y0"], core["y1"]), (core["x0"], core["x1"])
            tone = {"fill": core["fill"], "outline": None}
            notes.append(f"고정 문구 글로우 {glow} — 글자 몸 {core['x0']}~{core['x1']}×{core['y0']}~{core['y1']} 로 잼")
        else:
            tone = two_tone(frame_img, (cols[0], b[0], cols[1], b[1]), bg)
        cands, bsrc = band_font(frame_img, b, cols, txt, bg)
        # 잰 띠·가로 범위는 채움+외곽선 전체다. 렌더러는 외곽선을 글자 밖에 더 그리고(paint-order stroke),
        #   기울임은 글자 윗부분을 오른쪽으로 민다 — 그 둘을 빼고 '글자 몸'의 높이·폭·오른쪽 끝을 구한다.
        #   (2026-10-16 대조: 빼지 않아 [광고] 글자 높이 61 vs 원본 52~55, 오른쪽 끝이 화면 끝 1079에 닿았다)
        ital = italic_of(frame_img, [(b, cols)], bg, notes, "고정 문구")
        bfam = cands[0][0] if cands else fam
        o = (tone["outline"] or {}).get("px", 0)
        notes.append(f"고정 문구 글꼴 {bfam}·외곽선 {o}px — {bsrc}")
        body_h, body_w, lean = band_body(b, cols, o, ital)
        f2 = size_and_top(bfam, txt, b[0] + o, body_h, None)
        align = "right" if cols[1] > W * 0.7 else ("left" if cols[0] < W * 0.3 else "center")
        x = {"right": cols[1] - o - lean, "left": cols[0] + o, "center": (cols[0] + cols[1]) // 2}[align]
        layers.append({"kind": "text", "role": "brand", "text": txt, "x": x, "y": f2["y"], "w": body_w + 60,
                       "align": align, "lines": 1, "font": bfam, "size": f2["size"], "line_h": f2["line_h"],
                       "rgb": tone["fill"] or [128, 128, 128], "line_rgb": None, "outline": tone["outline"],
                       "shadow": None, "glow": glow, "box": None, "italic": ital,
                       "letter_spacing": spacing_for(bfam, f2["size"], txt, body_w) or 0, "enter": None})
    # 틀이 다른 구간 → template_off
    dur = float(pr.get("duration") or 0)
    tail = None
    for s0, s1 in L.get("other_frame_segments") or []:
        if dur and s1 >= dur - 0.3:
            start = s0
            if tail_probe is not None:
                start = refine_tail(tail_probe, max(0.0, s0 - 6.0), dur)
                if start is None:
                    start = s0; notes.append("틀 끝 시각 다시 찾기 실패 → 뜯기 값 그대로")
            tail = round(dur - start, 2)
        else:
            notes.append(f"틀이 다른 구간 {s0}~{s1} 은 끝 구간이 아님 — 설명서 시간 축(template_off.scenes)은 장면 번호라 자동 매핑 안 함")
    return {"canvas": [W, H], "layers": layers, "template_off": {"tail_sec": tail} if tail is not None else None,
            "made_by": schema.MADE_BY, "source": Path(str(J.get("source") or "")).stem or None,
            "made_from": {"tool": "tools/calcopy/engine/to_frame.py", "engine": J.get("engine"), "font": fnote, "title_ink_w": title_ink_w,
                          "font_confidence": fnote.get("font_confidence"), "notes": notes}}


def align_of(cols: list[tuple[int, int]], W: int) -> dict:
    """가로 범위들 → 정렬·x·w. 판단 순서:
    ① 3개 이상이고 왼쪽(오른쪽) 끝이 ALIGN_EDGE px 안으로 모이고 가운데는 흩어졌으면(> ALIGN_SPREAD) left(right)
    ② 가운데들의 중앙값이 화면 가운데 ± ALIGN_CENTER px 면 center — 한두 개가 영상 내용까지 잡혀 넓게 재여도(창 안 자막) 가운데
       (10-16 mY: 자막 상자 [7..742]·[192..917]·[238..843] — '모두 ±30' 규칙이 깨져 오른쪽 정렬 x917 로 냈다. 정답 가운데)
    ③ 그 밖은 왼쪽/오른쪽 끝 중 ALIGN_EDGE 안으로 모인 쪽(둘 다면 더 고른 쪽). 어느 끝도 안 모였으면 center — 끝이 안 모인 정렬은
       잰 상자가 흐린 것이다(10-16 1_V: 상자 끝 왼쪽 100~296·오른쪽 730~906 가 다 흩어졌는데 '덜 흩어진' 오른쪽으로 x906)."""
    if not cols:
        return {"x": W // 2, "w": W - 2 * SIDE_PAD, "align": "center"}
    centers = [(a + b) / 2 for a, b in cols]
    lefts, rights = [a for a, _ in cols], [b for _, b in cols]
    if len(cols) >= 3 and max(centers) - min(centers) > ALIGN_SPREAD:
        if max(lefts) - min(lefts) <= ALIGN_EDGE:
            return {"x": min(lefts), "w": W - min(lefts) - SIDE_PAD, "align": "left"}
        if max(rights) - min(rights) <= ALIGN_EDGE:
            return {"x": max(rights), "w": max(rights) - SIDE_PAD, "align": "right"}
    if abs(st.median(centers) - W / 2) <= ALIGN_CENTER:
        return {"x": W // 2, "w": W - 2 * SIDE_PAD, "align": "center"}
    sl, sr = max(lefts) - min(lefts), max(rights) - min(rights)
    if min(sl, sr) > ALIGN_EDGE:
        return {"x": W // 2, "w": W - 2 * SIDE_PAD, "align": "center"}
    if sl <= sr:
        return {"x": min(lefts), "w": W - min(lefts) - SIDE_PAD, "align": "left"}
    return {"x": max(rights), "w": max(rights) - SIDE_PAD, "align": "right"}


ANIM_TO_ENTER = {"확대/축소": "pop", "이동": "rise", "페이드/타자기": "fade", "없음": "none"}   # bench captions.caption_anim → 설명서 자막 등장
ENTER_MS = 300


def caption_enter_of(J: dict, notes: list) -> dict | None:
    """자막 등장 = 뜯기 caption_motion.starts 의 anim(bench 등장 종류) 최빈값. 판단 한 곳.
    '페이드/타자기'는 bench 가 둘을 못 가른다 → fade(타자 효과·커서는 따로 못 잼, 분석기 몫). 표본이 없으면 None."""
    import collections
    anims = [s.get("anim") for s in (J.get("caption_motion") or {}).get("starts") or [] if s.get("anim") in ANIM_TO_ENTER]
    if not anims:
        return None
    top, n = collections.Counter(anims).most_common(1)[0]
    kind = ANIM_TO_ENTER[top]
    notes.append(f"자막 등장 {kind} — 뜯기 등장 표본 {len(anims)}개 중 '{top}' {n}개" + (" (페이드/타자기 구분 못 함 → fade)" if top == "페이드/타자기" else ""))
    return {"kind": kind, "ms": ENTER_MS}


def caption_width_ref(fam: str, size: float, items: list, notes: list) -> dict | None:
    """자간 역산에 쓸 자막 하나 — 판단 한 곳. 잰 폭을 믿는 조건 둘:
      ① 폭 CAP_W_MIN 이상(짧은 자막은 잰 폭 몇 px 오차가 자간을 크게 흔든다)
      ② 잰 폭 / 그 글꼴로 그린 폭 의 비가 자막끼리 고르다(사분위 폭 / 중앙값 ≤ CAP_W_SPREAD, 3개 이상) — 잰 폭이 글 길이를 따르나.
    둘 다 맞으면 그 중 원래 순서 첫 자막, 아니면 None(자간·낱말 간격 0 — 글꼴 그대로).
    10-16 mY: 창 안 흰 자막(영상 위)이라 잰 폭이 영상 내용까지 잡혀 글 길이와 따로 놀았다('하키 경기 중' 6자 738px,
    '퍽을 기다리고 있었죠' 11자 673px) — 이걸로 자간 +26.6·낱말 −44.2 를 냈다. 정답 0·0."""
    font = _pil_font(fam, size)
    rs = []
    for it in items:
        if not it.get("text") or not it.get("widths") or int(it.get("lines") or 1) != 1:
            continue
        w, txt = it["widths"][0], it["text"][0]
        nat = font.getlength(txt)
        if w and nat and w >= CAP_W_MIN:
            rs.append((w / nat, it))
    n_all = sum(1 for it in items if it.get("widths"))
    if len(rs) < 3:
        notes.append(f"자막 자간·낱말 간격 0 — 폭 ≥{CAP_W_MIN}px 자막 {len(rs)}/{n_all}개(3개 미만)")
        return None
    rs.sort(key=lambda r: r[0])
    q = [r for r, _ in rs]
    spread = (q[(3 * len(q)) // 4] - q[len(q) // 4]) / max(1e-6, q[len(q) // 2])
    if spread > CAP_W_SPREAD:
        notes.append(f"자막 자간·낱말 간격 0 — 잰 폭이 글 길이를 안 따른다(잰 폭/그린 폭 사분위 폭 {spread:.2f} > {CAP_W_SPREAD}, "
                     f"{len(rs)}개) — 창 안 자막이 영상 내용까지 잡힌 것으로 본다")
        return None
    first = next(it for it in items if any(it is r[1] for r in rs))   # 원래 순서의 첫 자막(예전 판과 같은 기준 — ZdeZ 2판 값 유지)
    notes.append(f"자막 자간은 잰 폭 고른 {len(rs)}/{n_all}개(사분위 폭 {spread:.2f}) 중 첫 자막으로 역산")
    return first


def refine_tail(is_framed, t0: float, t1: float, step: float = 0.1) -> float | None:
    """[t0,t1) 를 step 간격으로 보며 틀이 있는 마지막 시각 + step = 틀이 사라지는 시각. 처음부터 없으면 None."""
    last = None
    t = t0
    while t < t1:
        if is_framed(t):
            last = t
        t = round(t + step, 3)
    return None if last is None else round(last + step, 2)


def ocr_fixed(img: np.ndarray, title_rows, brand_rows) -> tuple[dict | None, str | None]:
    """고정 띠 글자를 무료 제미나이로 읽는다(gemini_free.ask 재사용)."""
    import cv2
    from tools.calcopy.engine.gemini_free import ask
    parts = []
    def jpg(a):
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(a, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes()
    if title_rows:
        parts += ["제목 띠:", jpg(img[max(0, title_rows[0][0] - 10):title_rows[-1][1] + 10])]
    if brand_rows:
        parts += ["고정 문구 띠:", jpg(img[max(0, brand_rows[0][0] - 6):brand_rows[0][1] + 6])]
    prompt = ('그림 속 한국어 글자를 그대로 옮겨 적어라(고치지 말고, 줄바꿈은 그림대로). JSON: '
              '{"title": ["제목 1줄", "제목 2줄", ...], "brand": "고정 문구 띠 글자 또는 null"}')
    d, err = ask(parts, prompt, tag="frame_ocr")
    if not d:
        return None, err
    return {"title": [str(x) for x in d.get("title") or []], "brand": d.get("brand") or None, "_model": d.get("_model")}, None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("tteutgi"); ap.add_argument("--out", required=True); ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--at", type=float, default=None, help="틀이 있는 원본 프레임 시각(기본 = 첫 정상 구간 + 1초)")
    ap.add_argument("--title-font", help="제목 글꼴을 판별 대신 이 등록 글꼴로(하위 스타일에서 확정한 값 — 크기 역산도 이 글꼴로)")
    ap.add_argument("--ocr-from", help="고정 띠 글자를 다시 읽지 않고 이 설명서(frame.json)의 제목·고정 문구 글을 쓴다(제미나이 한도 소진 때)")
    a = ap.parse_args(argv)
    J = json.loads(Path(a.tteutgi).read_text(encoding="utf-8"))
    dur0 = float((J.get("probe") or {}).get("duration") or 0)
    if any(s1 < dur0 - 0.3 for _, s1 in (J.get("layout") or {}).get("other_frame_segments") or []):
        # 끝이 아닌 틀 구간(훅 카드 등)이 있으면 틀 여러 장 설명서로 — to_frame_multi 가 맡는다(판단 한 곳).
        #   --ocr-from 은 "hook=a.json,body=b.json" 꼴(틀마다 예전 설명서)
        from tools.calcopy.engine import to_frame_multi
        argv2 = [a.tteutgi, "--out", a.out] + (["--ocr-from", *a.ocr_from.split(",")] if a.ocr_from and "=" in a.ocr_from else [])
        return to_frame_multi.main(argv2)
    from shopping_shorts.channelkit.bench import probe
    src = J.get("source")
    pr = J.get("probe") or {}
    W, H = int(pr.get("w") or 1080), int(pr.get("h") or 1920)
    L = J.get("layout") or {}
    img = None
    if src and Path(src).exists():
        main_segs = ((L.get("bench_full_single") or {}).get("frame_segments") or {}).get("main") or [[0, 0]]
        t = a.at if a.at is not None else main_segs[0][0] + 1.0
        img = probe.grab(src, t, f"scale={W}:{H}", W, H)
    ocr, err = None, None
    if a.ocr_from:   # 예전 설명서의 OCR 글 재사용 — 글자 내용만 쓰고 자리·크기는 이번에 다시 잰다
        old = json.loads(Path(a.ocr_from).read_text(encoding="utf-8"))
        t_old = next((l for l in old.get("layers", []) if l.get("role") == "title"), {}).get("text")
        b_old = next((l for l in old.get("layers", []) if l.get("role") == "brand"), {}).get("text")
        ocr = {"title": t_old.split("\n") if t_old else [], "brand": b_old, "_model": "ocr-from " + Path(a.ocr_from).name}
    elif img is not None and not a.no_ocr:
        bands = sorted(tuple(b) for b in L.get("above_bands") or [])
        bg = L.get("bg_rgb")
        brand = [b for b in bands if b[0] < BRAND_TOP * H and (lambda c: c and c[1] - c[0] < BRAND_MAX_W * W)(ink_columns(img, b[0], b[1], bg))]
        title = [b for b in bands if b not in brand]
        ocr, err = ocr_fixed(img, title, brand)
    probe_fn = None
    if src and Path(src).exists() and L.get("bg_rgb"):
        rows = gap_rows(L.get("window"), [tuple(b) for b in L.get("above_bands") or []])
        probe_fn = lambda t: (lambda f: f is not None and framed(f, rows, L["bg_rgb"]))(probe.grab(src, t, f"scale={W}:{H}", W, H))  # noqa: E731
    pol = L.get("ink_polarity") or "dark"            # build 의 자막 극성과 같은 값
    gap = caption_word_gap(src, J, W, H, pol) if src and Path(src).exists() else None
    F = build(J, img, ocr, probe_fn, gap, title_font_fixed=a.title_font)
    if err:
        F["made_from"]["notes"].append(f"고정 띠 OCR 실패: {err}")
    if ocr:
        F["made_from"]["ocr_model"] = ocr.get("_model")
    schema.validate(F)      # 형식 검사 — 통과 못 하면 여기서 멈춘다(조용히 쓰지 않는다)
    Path(a.out).write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(F["made_from"], ensure_ascii=False, indent=1))
    print("frame:", a.out)


if __name__ == "__main__":
    main()
