# -*- coding: utf-8 -*-
"""샥탬스토리 자막 그림 — 낱말별 강조 색 + 같은 색 번짐 빛 + 흰 글자 그림자 + 넘김 가로 흐림 (관제 097, 2026-10-18).

(판단 주인: 자막 한 장의 모양) caption_image() 한 곳. 값은 전부 rules.json caption 절(벤치 QMJ 실측) — 코드에 숫자 박지 않는다.
어느 낱말을 칠하나는 emph.py(대본 emph 칸)가 정하고, 여기는 받은 (덩어리, 색)을 그대로 그린다.
render.py 는 fx.build_layer 를 통해 이걸 부르기만 한다.

    PYTHONUTF8=1 py tools/calcopy/shark/caption_style.py demo <out.png>   # 벤치 QMJ 3.25 '15L 물을 빨아들이는' 재현 견본
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RULES = Path(__file__).with_name("rules.json")
BAND = (760, 1200)   # 그리는 띠(두 줄 잉크 895~1022·크게 85px·번짐 30px 를 덮음) — 자리 판단 아님, 계산 범위(속도)


@lru_cache(maxsize=1)
def rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def _font(size: int):
    from PIL import ImageFont
    from tools.calcopy import narr_video as nv
    return ImageFont.truetype(nv._font_file(rules()["caption"]["font"]), size)


def segments(text: str, emph: list[dict] | None) -> list[tuple[str, str | None]]:
    """글 → [(조각, 색 이름|None)]. emph = [{"span": 칠할 글, "color": 색 이름}] — span 이 글에 없으면 멈춘다(조용히 흰 글자로 내려가지 않는다)."""
    marks = []
    for e in emph or []:
        s = e["span"]
        i = text.find(s)
        if i < 0:
            raise ValueError(f"강조 '{s}' 가 자막 '{text}' 에 없음")
        marks.append((i, i + len(s), e["color"]))
    marks.sort()
    out, k = [], 0
    for a, b, c in marks:
        if a > k:
            out.append((text[k:a], None))
        out.append((text[a:b], c)); k = b
    if k < len(text):
        out.append((text[k:], None))
    return [x for x in out if x[0]]


def _wrap(segs, font, max_w):
    """한 줄 폭이 max_w 를 넘으면 가운데 가까운 띄어쓰기에서 두 줄로(벤치 2줄 칸 = 각 줄 가운데 맞춤)."""
    text = "".join(s for s, _ in segs)
    if font.getlength(text) <= max_w or " " not in text:
        return [segs]
    sp = [i for i, ch in enumerate(text) if ch == " "]
    cut = min(sp, key=lambda i: abs(i - len(text) / 2))
    l1, l2, k = [], [], 0
    for s, c in segs:
        a, b = k, k + len(s); k = b
        if b <= cut:
            l1.append((s, c))
        elif a > cut:
            l2.append((s, c))
        else:
            l1.append((s[:cut - a], c)); l2.append((s[cut - a + 1:], c))
    return [[x for x in l1 if x[0]], [x for x in l2 if x[0]]]


def caption_image(text: str, emph: list[dict] | None = None, big: bool = False):
    """(판단 주인) 1080×1920 RGBA 한 장. 줄 잉크 세로 = rules one_line_ink(한 줄)·two_line_ink(두 줄)의 가운데."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    R = rules()["caption"]
    pal = R["palette"]
    size = int(round(R["size"] * (R["big_scale"] if big else 1.0)))
    font = _font(size)
    lines = _wrap(segments(text, emph), font, R["max_w"])
    if len(lines) == 1:
        centers = [sum(R["one_line_ink"]) / 2]
    else:
        centers = [sum(r) / 2 for r in R["two_line_ink"]]
    W, H = 1080, BAND[1] - BAND[0]
    white_m = Image.new("L", (W, H), 0)
    col_m = {}   # 색 이름 → 마스크
    for ln, cy in zip(lines, centers):
        full = "".join(s for s, _ in ln)
        # 잉크 세로 가운데를 cy 에: 한글 잉크 상자(전체 글)의 가운데를 맞춘다
        bx = font.getbbox(full, anchor="ls")
        y_base = cy - BAND[0] - (bx[1] + bx[3]) / 2
        x = 540 - font.getlength(full) / 2
        for s, c in ln:
            m = white_m if c is None else col_m.setdefault(c, Image.new("L", (W, H), 0))
            ImageDraw.Draw(m).text((x, y_base), s, font=font, fill=255, anchor="ls")
            x += font.getlength(s)
    all_m = white_m.copy()
    for m in col_m.values():
        all_m = ImageChops.lighter(all_m, m)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def layer(mask, rgb, alpha, dx=0, dy=0, blur=0.0, dilate=0):
        m = mask
        if dilate:
            m = m.filter(ImageFilter.MaxFilter(2 * dilate + 1))
        if dx or dy:
            m = ImageChops.offset(m, int(dx), int(dy))
        if blur:
            m = m.filter(ImageFilter.GaussianBlur(blur))
        a = m.point(lambda v: int(v * alpha))
        im = Image.new("RGBA", (W, H), tuple(int(v) for v in rgb) + (0,))
        im.putalpha(a)
        out.alpha_composite(im)

    sh, gl, ed = R["shadow"], R["glow"], R["edge"]
    layer(all_m, (0, 0, 0), sh["alpha"], sh["dx"], sh["dy"], sh["blur"] / 2)
    for c, m in col_m.items():
        layer(m, pal[c], gl["alpha"], blur=gl["blur"], dilate=gl["dilate"])
    for c, m in col_m.items():
        layer(m, (0, 0, 0), ed["alpha"], ed["dx"], ed["dy"], ed["blur"])
    layer(white_m, R["white"], 1.0)
    for c, m in col_m.items():
        layer(m, pal[c], 1.0)
    full = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    full.paste(out, (0, BAND[0]))
    return full


def hblur(im, px: int):
    """넘김 가로 흐림(rules caption.transition) — 가로 상자 흐림 px."""
    if px <= 1:
        return im
    a = np.asarray(im).astype(np.float32)
    k = int(px)
    c = np.cumsum(np.pad(a, ((0, 0), (k, k), (0, 0)), mode="edge"), axis=1)
    b = (c[:, 2 * k:] - c[:, :-2 * k]) / (2 * k)
    from PIL import Image
    return Image.fromarray(b[:, :a.shape[1]].clip(0, 255).astype(np.uint8), "RGBA")


def main():
    if sys.argv[1] == "demo":
        im = caption_image("15L 물을 빨아들이는", [{"span": "빨아들이는", "color": "초록"}])
        im.save(sys.argv[2])
        print(sys.argv[2])


if __name__ == "__main__":
    main()
