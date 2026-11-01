# -*- coding: utf-8 -*-
"""샥탬스토리 꾸밈 대조 시트 — 편의 꾸밈이 나오는 모든 순간을 벤치 같은 종류 꾸밈과 나란히(창 전체 + 확대 크롭) (관제 097, 2026-10-18).

한 줄 = 꾸밈 하나: [벤치 창 | 우리 창 | 벤치 확대 | 우리 확대]. 빨간 원 줄은 확대에 얼굴 상자(하늘색)·눈(노랑)·맞춘 원 중심(분홍)을 그린다.
벤치 기준 프레임 = rules.json effects.<kind>.bench_ref [id, 초, [x,y]] (실측 대표 프레임).

    PYTHONUTF8=1 py tools/calcopy/shark/fx_sheet.py <final.mp4> <render_info.json> <out.jpg> [--title 1편]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.shark.caption_style import rules  # noqa: E402
from tools.calcopy.shark import fx_measure as M  # noqa: E402

LOOK = {"red_circle": 0.25, "arrow_green_down": 0.25, "dashed_circle": 0.8, "arrow_pink_up": 0.4, "arrow_curve_red": 0.6,
        "money_emoji": 0.4, "emoji": 0.4, "flash": 0.0}
ZOOM = 520     # 확대 크롭 한 변(완성본 px)
TW, TH = 330, 321


def grab(src, t) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{max(0, t):.3f}", "-i", str(src), "-frames:v", "1", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True)
    return np.frombuffer(r.stdout[:1080 * 1920 * 3], np.uint8).reshape(1920, 1080, 3)


def tiles(a: np.ndarray, at, label, face=False):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 20)
    win = Image.fromarray(a[434:1486]).resize((TW, TH))
    x, y = int(at[0]), int(at[1])
    x0 = min(max(0, x - ZOOM // 2), 1080 - ZOOM); y0 = min(max(434, y - ZOOM // 2), 1486 - ZOOM)
    z = Image.fromarray(a[y0:y0 + ZOOM, x0:x0 + ZOOM].copy())
    d = ImageDraw.Draw(z)
    note = ""
    if face:
        R = M.ring(a)
        fs = M.faces(a)
        F = M.face_near(R, fs) if R else (fs[0] if fs else None)
        if F:
            d.rectangle([F["x"] - x0, F["y"] - y0, F["x"] + F["w"] - x0, F["y"] + F["h"] - y0], outline=(0, 220, 255), width=3)
            ex, ey = F["eye"]; d.ellipse([ex - x0 - 6, ey - y0 - 6, ex - x0 + 6, ey - y0 + 6], fill=(255, 255, 0))
        if R:
            d.ellipse([R["cx"] - x0 - 7, R["cy"] - y0 - 7, R["cx"] - x0 + 7, R["cy"] - y0 + 7], fill=(255, 0, 255))
        if R and F:
            rel = M.relation(R, F)
            note = f" 어긋남{rel['off_fh']:.2f} r/얼굴{rel['r_fh']:.2f} 얼굴/창{rel['face_h_win']:.2f} 안{rel['face_inside']:.2f}"
    z = z.resize((TH, TH))
    for im, s in ((win, label), (z, "확대" + note)):
        ImageDraw.Draw(im).text((4, 2), s, font=font, fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
    return win, z


def build(final: Path, info: dict, dst: Path, title: str = ""):
    from PIL import Image, ImageDraw, ImageFont
    E = rules()["effects"]
    rows = []
    bench_cache = {}
    from tools.calcopy.shark import fx as FX
    for e in sorted(FX.timed(info), key=lambda e: e["T"][0]):   # 렌더가 실제로 그린 시각(번쩍 = 컷 프레임에 붙임·점선 원 = 컷 끝까지)
        k = e["kind"]
        ref = (E.get(k) or {}).get("bench_ref") or E["flash"]["bench_ref"]
        if k == "flash":
            ref = E["flash"]["bench_ref_by_color"].get(e.get("color", "초록"), ref)
        bid, bt, bat = ref
        if (bid, bt) not in bench_cache:
            bench_cache[(bid, bt)] = grab(M.BENCH_DIR / f"{bid}.mp4", bt)
        t = e["T"][0] + LOOK.get(k, 0.3) + (1 / 60 if k == "flash" else 0)   # 번쩍 첫 프레임(반 프레임 뒤를 집어 앞 프레임을 피함)
        a = grab(final, t)
        bw, bz = tiles(bench_cache[(bid, bt)], bat, f"벤치 {bid[:3]} {bt:.2f} {k}", face=k == "red_circle")
        ow, oz = tiles(a, e["at"], f"{title} {e['line']} {t:.2f} {k}{' ' + e.get('color', '') if k == 'flash' else ''}", face=k == "red_circle")
        rows.append((bw, ow, bz, oz))
    W = TW * 2 + TH * 2 + 30
    sh = Image.new("RGB", (W, len(rows) * (TH + 6) + 40), (25, 25, 25))
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 24)
    ImageDraw.Draw(sh).text((8, 6), f"{title} 꾸밈 대조 — 벤치 | 우리 | 벤치 확대 | 우리 확대 (하늘색=얼굴 상자, 노랑=눈, 분홍=원 중심)", font=font, fill=(255, 255, 255))
    for i, (bw, ow, bz, oz) in enumerate(rows):
        y = 40 + i * (TH + 6)
        sh.paste(bw, (0, y)); sh.paste(ow, (TW + 6, y)); sh.paste(bz, (2 * TW + 18, y)); sh.paste(oz, (2 * TW + TH + 24, y))
    sh.save(dst, quality=88)
    return dst


def main():
    final, info, dst = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), Path(sys.argv[3])
    title = sys.argv[sys.argv.index("--title") + 1] if "--title" in sys.argv else ""
    print(build(final, info, dst, title))


if __name__ == "__main__":
    main()
