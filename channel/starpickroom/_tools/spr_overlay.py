# -*- coding: utf-8 -*-
"""스타픽룸 틀의 '엔진 설명서가 못 그리는 층' 그림(투명 PNG 1080×1920) — 관제 097.
    PYTHONUTF8=1 py channel/starpickroom/_tools/spr_overlay.py <title.json> <out.png>
title.json = {"lines":[[["불 없이 5분 완성!",[255,255,255]]], [["주상욱도 극찬한 ",[255,255,255]],["비빔국수",[203,3,252]]]], "watermark":"얜샷템", "logo":"얜샷템"}

왜 따로 그리나(엔진 결함·빈칸 — 보고함):
  ① 제목 낱말별 색: calcopy_frame 스키마는 줄 색(line_rgb)만 있다. 벤치는 줄 안 일부 낱말만 노랑 #FDF702 / 보라 #CF04FC.
  ② 창 안 반투명 워터마크: 글자 층에 투명도 칸이 없다(벤치 '스타픽룸' 흰 글 약 55% 불투명, 창 오른쪽 위 x790~1030 y525~575).
  ③ 금색 로고: image 층은 있으나 렌더 경로에서 로컬 그림 경로가 읽히는지 확인 안 됨 → 합성에서 덮는다.
실측 근거(VbpdNba182M 9.6초·19.2초 프레임, 21VoGAEK·ASqF·j5D 줄판독):
  제목 Cafe24Ohsquare 기울임 +10° · 잉크 y244~429 · 두 줄 가운데 · 크기 약 92px(줄 높이 107) · 흰 [252,252,252] 바탕 글 + 강조 낱말
  로고 y1666~1919 금색(중앙값 [229,188,113]) · 글 오른쪽 x460~1000 · 별 3~4개 · 휘어진 꼬리 + 별 1개
"""
import json, math, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import to_frame as T  # noqa: E402

W, H = 1080, 1920
TITLE = dict(font="Cafe24Ohsquare", px=92, centers=[288, 392], shear=math.tan(math.radians(10)), max_w=1030)
WM = dict(font="GmarketSansBold", px=56, x1=1030, cy=550, alpha=140)
LOGO = dict(font="GmarketSansBold", px=190, box=(440, 1700, 1020, 1915))   # 벤치 글 x460~1000


def _font(fam, px):
    return T._pil_font_px(fam, int(px))


def rgb_of(c):
    """[r,g,b] 또는 '#RRGGBB' → (r,g,b)."""
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(c, str) else tuple(c)


def italic_line(segs, fam, px, shear):
    """한 줄 = [(글, rgb)…] → 기울인 RGBA 그림."""
    f = _font(fam, px)
    total = sum(f.getlength(t) for t, _ in segs)
    asc, desc = f.getmetrics()
    pad = int(px * 0.4)
    im = Image.new("RGBA", (int(total) + 2 * pad + int((asc + desc) * shear), asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im); x = pad + int((asc + desc) * shear * 0.5)
    for t, rgb in segs:
        d.text((x, pad), t, font=f, fill=rgb_of(rgb) + (255,))
        x += f.getlength(t)
    # 위쪽을 오른쪽으로 민다(기울임 +10°)
    return im.transform(im.size, Image.AFFINE, (1, shear, -shear * im.size[1] * 0.5, 0, 1, 0), resample=Image.BICUBIC)


def title_layer(canvas, lines):
    for segs, cy in zip(lines, TITLE["centers"]):
        px = TITLE["px"]
        while True:
            im = italic_line(segs, TITLE["font"], px, TITLE["shear"])
            bb = im.getbbox()
            if bb[2] - bb[0] <= TITLE["max_w"] or px < 50:
                break
            px -= 2
        im = im.crop(bb)
        canvas.alpha_composite(im, (W // 2 - im.size[0] // 2, cy - im.size[1] // 2))


def watermark_layer(canvas, text):
    f = _font(WM["font"], WM["px"])
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    w = f.getlength(text); bb = f.getbbox(text)
    d.text((WM["x1"] - w, WM["cy"] - (bb[1] + bb[3]) // 2), text, font=f, fill=(255, 255, 255, WM["alpha"]))
    canvas.alpha_composite(im)


def star(d, cx, cy, r, fill, points=5, inner=0.45, rot=-90):
    pts = []
    for i in range(points * 2):
        rr = r if i % 2 == 0 else r * inner
        a = math.radians(rot + i * 180 / points)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def gold(size):
    """세로 금색 그라데이션(밝은 위 → 진한 아래)."""
    g = Image.new("RGBA", size)
    top, mid, bot = (255, 244, 200), (240, 203, 125), (196, 140, 58)
    for y in range(size[1]):
        k = y / max(1, size[1] - 1)
        c = [int(top[i] + (mid[i] - top[i]) * k * 2) if k < 0.5 else int(mid[i] + (bot[i] - mid[i]) * (k - 0.5) * 2) for i in range(3)]
        ImageDraw.Draw(g).line([(0, y), (size[0], y)], fill=tuple(c) + (255,))
    return g


def logo_layer(canvas, text):
    x0, y0, x1, y1 = LOGO["box"]
    f = _font(LOGO["font"], LOGO["px"])
    mask = Image.new("L", (W, H), 0); dm = ImageDraw.Draw(mask)
    w = f.getlength(text); bb = f.getbbox(text)
    tx, ty = (x0 + x1) // 2 - w // 2, (y0 + y1) // 2 + 20 - (bb[1] + bb[3]) // 2
    dm.text((tx, ty), text, font=f, fill=255)
    shadow = Image.new("RGBA", (W, H), (60, 35, 5, 0)); shadow.putalpha(mask.filter(ImageFilter.MaxFilter(7)))
    canvas.alpha_composite(shadow)
    ty0, ty1 = int(ty + bb[1]), int(ty + bb[3])          # 그라데이션은 글자 높이 안에서(밝은 위 → 진한 아래, 벤치 로고)
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g.paste(gold((W, ty1 - ty0 + 1)), (0, ty0))
    g.putalpha(mask); canvas.alpha_composite(g)
    d = ImageDraw.Draw(canvas)
    # 휘어진 꼬리 + 큰 별(벤치 로고 오른쪽 위), 반짝이 별 3개
    gx, gy = tx + w - 40, ty + bb[1] - 40
    d.arc([gx - 330, gy - 30, gx + 40, gy + 160], 205, 300, fill=(240, 205, 130, 255), width=6)
    star(d, gx + 30, gy - 10, 34, (245, 210, 120, 255))
    for cx, cy, r in [(110, 1790, 16), (430, 1890, 12), (980, 1880, 14), (250, 1720, 10)]:
        star(d, cx, cy, r, (240, 210, 140, 255), points=4, inner=0.25)


def build(spec: dict, out: Path):
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    title_layer(canvas, spec["lines"])
    if spec.get("watermark"):
        watermark_layer(canvas, spec["watermark"])
    if spec.get("logo"):
        logo_layer(canvas, spec["logo"])
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


if __name__ == "__main__":
    build(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]))
    print("ok", sys.argv[2])
