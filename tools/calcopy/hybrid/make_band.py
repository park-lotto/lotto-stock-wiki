# -*- coding: utf-8 -*-
"""판 맨 위 그림 띠(로고 자리) 만들기 — 글자 없는 우리 그림, 색감·아래 페이드만 벤치 실측에 맞춘다(별헤는쏭판 10-27).
    PYTHONUTF8=1 py tools/calcopy/hybrid/make_band.py <out.png> [--seed 27] [--ref <벤치 프레임.png>]
벤치 실측(별헤는쏭 1lMb 6.0초 y0~235): 평균 RGB (70,53,64) · 아래로 검정에 스며듦(y200 (33,23,31) → y234 (11,6,12)).
픽셀 자(bands.measure_video)가 띠를 제목 칸과 한 덩어리로 읽으려면 아래 끝이 검정으로 이어져야 한다(10-27: 밝은 채 끊긴 띠는 별 무늬를 제목 글자로 잼)."""
import argparse
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 235
TARGET_MEAN = (70, 53, 64)


def make(out: str, seed: int = 27, ref: str | None = None) -> None:
    random.seed(seed)
    im = Image.new("RGBA", (W, H), (22, 16, 34, 255))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(18):                                   # 분홍·주황·남색 구름(벤치 결 — 연기 띠)
        cx, cy, rr = random.randint(-80, W + 80), random.randint(-20, H), random.randint(90, 210)
        col = random.choice([(214, 120, 120), (230, 150, 110), (160, 90, 150), (70, 60, 140), (200, 110, 160)])
        d.ellipse([cx - rr, cy - rr // 2, cx + rr, cy + rr // 2], fill=col + (110,))
    im = Image.alpha_composite(im, lay.filter(ImageFilter.GaussianBlur(34)))
    hexl = Image.new("RGBA", (W, H), (0, 0, 0, 0))       # 흐린 육각형 무늬(벤치 그림 띠 결) — 모든 줄에 무늬가 있어야 픽셀 자가 띠를 한 덩어리로 읽는다(10-27 빈 줄에서 띠가 3개로 끊김)
    dh = ImageDraw.Draw(hexl)
    r = 46
    for row in range(-1, H // int(r * 1.5) + 2):
        for col in range(-1, W // int(r * 1.732) + 2):
            cx = col * r * 1.732 + (r * 0.866 if row % 2 else 0)
            cy = row * r * 1.5
            pts = [(cx + r * math.cos(math.radians(60 * k + 30)), cy + r * math.sin(math.radians(60 * k + 30))) for k in range(6)]
            dh.polygon(pts, outline=(255, 220, 200, 22), width=2)
    im = Image.alpha_composite(im, hexl)
    d = ImageDraw.Draw(im)
    for _ in range(60):
        x, y, s = random.randint(0, W), random.randint(0, H - 40), random.choice([1, 1, 2, 3])
        d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 238, 200, random.randint(120, 255)))
    f = ImageFont.truetype("C:/Windows/Fonts/seguisym.ttf", 110)
    for ch, x, y, c in [("\u266B", 470, 30, (252, 214, 140, 255)), ("\u266A", 360, 80, (250, 190, 205, 235)), ("\u2669", 610, 85, (205, 220, 255, 230)),
                        ("\u266C", 120, 50, (255, 225, 170, 190)), ("\u266A", 920, 60, (230, 200, 250, 190))]:
        gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(gl).text((x, y), ch, font=f, fill=c)
        im = Image.alpha_composite(im, gl.filter(ImageFilter.GaussianBlur(7)))
        im = Image.alpha_composite(im, gl)
    im = im.convert("RGB")
    if ref:                                               # 줄마다 밝기 = 벤치 띠 같은 줄 밝기(아래로 검정에 스며드는 곡선을 그대로 — 픽셀 자가 띠를 한 덩어리로 읽는다)
        import numpy as np
        R = np.asarray(Image.open(ref).convert("RGB"), np.float64)[:H]
        A = np.asarray(im, np.float64)
        k = R.mean(axis=(1, 2)) / np.maximum(1e-6, A.mean(axis=(1, 2)))
        im = Image.fromarray(np.clip(A * k[:, None, None], 0, 255).astype(np.uint8))
    m = [sum(c) / (W * H) for c in zip(*im.get_flattened_data())] if hasattr(im, "get_flattened_data") else [sum(c) / (W * H) for c in zip(*im.getdata())]   # 평균 색을 벤치 평균에 맞춘다(채널별 배율)
    gain = [t / max(1e-6, v) for t, v in zip(TARGET_MEAN, m)]
    im = Image.eval(im, lambda v: v)
    im = Image.merge("RGB", [ch.point(lambda v, g=g: min(255, int(v * g))) for ch, g in zip(im.split(), gain)])
    im.save(out)
    print(out, "평균", [round(v * g) for v, g in zip(m, gain)])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--seed", type=int, default=27); ap.add_argument("--ref", help="벤치 한 프레임 png — 줄마다 밝기를 그 띠에 맞춘다")
    a = ap.parse_args()
    make(a.out, a.seed, a.ref)
