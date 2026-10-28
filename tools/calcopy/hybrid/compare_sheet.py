# -*- coding: utf-8 -*-
"""벤치 ↔ 우리 판 나란히 시트(눈 확인용) — 위 줄 = 본보기 벤치 편(배치가 고른 편), 아래 줄 = 우리 완성본 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/compare_sheet.py <판> <doc_dir> <work_dir> [--n 10] [--bench <id>]

같은 비율 시각(0%·10%·…)으로 두 영상에서 프레임을 뽑아 270×480 칸으로 붙인다. 칸 위에 초를 적는다.
결과 = <doc>/벤치대조_시트.jpg (+ 자막 등장 확대 띠 <doc>/벤치대조_등장.jpg — 두 영상 첫 자막 덩어리 0~0.5초 30fps 6칸).
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import dur_of, jload  # noqa: E402

CW, CH = 270, 480


def grab(mp4, t, size=(CW, CH)):
    from PIL import Image
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={size[0]}:{size[1]}",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return Image.open(io.BytesIO(b)).convert("RGB") if b else Image.new("RGB", size, (60, 0, 0))


def sheet(style_name: str, doc: Path, work: Path, n: int = 10, bench_id: str | None = None) -> Path:
    from PIL import Image, ImageDraw
    from tools.calcopy.hybrid import styles as ST
    st = ST.load(style_name)
    tab = jload(Path(work) / "render" / "자막표.json")
    bid = bench_id or tab["check"]["reference"]
    bench = Path(st["bench"]["src_dir"]) / f"{bid}.mp4"
    ours = Path(work) / "render" / "final.mp4"
    db, do = dur_of(bench), dur_of(ours)
    out = Image.new("RGB", (CW * n, CH * 2 + 60), (16, 16, 16))
    d = ImageDraw.Draw(out)
    from PIL import ImageFont
    fnt = ImageFont.truetype(str(Path(__file__).resolve().parents[3] / "shopping_shorts/static/fonts/Pretendard-Bold.otf"), 20)
    d.text((6, 4), f"위 = 벤치 {st['bench']['channel']} {bid} ({db:.1f}초) · 아래 = 우리 {style_name} ({do:.1f}초) — 같은 비율 시각", fill=(255, 230, 0), font=fnt)
    for k in range(n):
        p = (k + 0.5) / n
        for row, (mp4, dur) in enumerate(((bench, db), (ours, do))):
            im = grab(mp4, p * dur)
            out.paste(im, (k * CW, 30 + row * (CH + 30)))
            d.text((k * CW + 4, 30 + row * (CH + 30) + CH + 4), f"{p * dur:.1f}s", fill=(200, 200, 200))
    dst = Path(doc) / "벤치대조_시트.jpg"
    out.save(dst, quality=85)
    # 첫 자막 등장 0~0.2초(30fps 7칸) — 벤치 첫 덩어리 시각은 줄판독 첫 행, 우리는 자막표 첫 행
    lr = jload(Path(st["bench"]["line_reads"]) / f"{bid}.json") if (Path(st["bench"]["line_reads"]) / f"{bid}.json").exists() else None
    tb = float((lr or {}).get("lines", [{}])[0].get("t0", 0.0)) if lr else 0.0
    to = float(tab["rows"][0]["t0"]) if tab.get("rows") else 0.0
    strip = Image.new("RGB", (CW * 7, CH * 2 + 30), (16, 16, 16))
    ds = ImageDraw.Draw(strip)
    for k in range(7):
        for row, (mp4, t0) in enumerate(((bench, tb), (ours, to))):
            strip.paste(grab(mp4, t0 + k / 30), (k * CW, row * (CH + 15)))
        ds.text((k * CW + 4, CH + 1), f"+{k}f", fill=(255, 230, 0))
    dst2 = Path(doc) / "벤치대조_등장.jpg"
    strip.save(dst2, quality=85)
    return dst


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("style"); ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--n", type=int, default=10); ap.add_argument("--bench")
    a = ap.parse_args()
    print(sheet(a.style, Path(a.doc), Path(a.work), a.n, a.bench))
