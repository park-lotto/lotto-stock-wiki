"""확대 이어받기 렌더 실측 — 같은 영상을 두 칸(0.8초+1.1초)으로 나눠 zoom_move_vf 로 굽고, 칸 경계(앞 칸 마지막 프레임 vs 뒤 칸 첫 프레임)
픽셀 차이를 잰다. 고치기 전(뒤 칸 확대 없음=1배) / 고친 뒤(zoom_runs 로 이어받기) 둘 다 찍는다.
실행: py tools/scene_font_research/check_zoom_runs_render.py <작업폴더>"""
import subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts.scene_style import zoom_runs, zoom_move_vf
W, H = 540, 500
work = Path(sys.argv[1] if len(sys.argv) > 1 else "zoomrun_check"); work.mkdir(exist_ok=True)
src = work / "src.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=30:d=2", str(src)], check=True)
sc = [{"start": 0, "end": .8, "beat_idx": 1}, {"start": .8, "end": 1.9, "beat_idx": 1}]
ef = {"0": {"zoom": 1.3, "zoomIn": .5, "zoomMove": "inout", "panX": .2}}

def part(effect, a, b, frames, skip, name):
    z = float(effect.get("zoom") or 1); zw, zh = round(W * z / 2) * 2, round(H * z / 2) * 2
    cx = round((zw - W) * (1 - effect.get("panX", 0)) / 2); cy = round((zh - H) * (1 - effect.get("panY", 0)) / 2)
    vf = zoom_move_vf(effect, W, H, zw, zh, cx, cy, frames, skip)
    out = work / f"{name}_%03d.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a), "-t", str(b - a), "-i", str(src), "-vf", vf, str(out)], check=True)
    return sorted(work.glob(f"{name}_*.png"))

def diff(p, q):
    return float(np.abs(np.asarray(Image.open(p), float) - np.asarray(Image.open(q), float)).mean())

import os
Z = {"zoom": 1.3, "zoomIn": .5, "zoomMove": os.environ.get("WAY", "in"), "panX": .2}
print("확대 방식", Z["zoomMove"])
inner = None
# 경우: 둘째 칸 확대 없음 / 둘째 칸도 같은 확대(칸마다 다시 시작하던 것) / 자막 3칸
for name, sc, ef in (("둘째 칸 확대 없음", sc, {"0": Z}),
                     ("두 칸 모두 확대", sc, {"0": Z, "1": Z}),
                     ("자막 3칸", [{"start": 0, "end": .6, "beat_idx": 1}, {"start": .6, "end": 1.2, "beat_idx": 1}, {"start": 1.2, "end": 1.9, "beat_idx": 1}], {"0": Z, "2": Z})):
    runs = zoom_runs(sc, ef); news, olds = [], []
    for k, s_ in enumerate(sc):
        n = round((s_["end"] - s_["start"]) * 30)
        news.append(part(runs[k][0], s_["start"], s_["end"], round(runs[k][2] * 30), round(runs[k][1] * 30), f"n{name}{k}"))
        olds.append(part(ef.get(str(k), {}), s_["start"], s_["end"], n, 0, f"o{name}{k}"))
    if inner is None:
        inner = np.mean([diff(news[0][k], news[0][k + 1]) for k in range(len(news[0]) - 1)]); print(f"칸 안 프레임 간 평균 차이 {inner:.1f}")
    o = max(diff(olds[k][-1], olds[k + 1][0]) for k in range(len(sc) - 1)); w = max(diff(news[k][-1], news[k + 1][0]) for k in range(len(sc) - 1))
    print(f"[{name}] 경계 차이 최대: 고치기 전 {o:.1f} / 고친 뒤 {w:.1f}")

# 확대가 컷 안에서 몇 번 '다시 시작'하나(배율이 줄었다 다시 커지는 횟수) — inout 처럼 경계 픽셀은 같아도 다시 확대되는 것을 잡는다
from shopping_shorts.scene_style import zoom_curve
for name, sc, ef in (("두 칸 모두 확대", [{"start": 0, "end": .8, "beat_idx": 1}, {"start": .8, "end": 1.9, "beat_idx": 1}], {"0": Z, "1": Z}),
                     ("자막 3칸", [{"start": 0, "end": .6, "beat_idx": 1}, {"start": .6, "end": 1.2, "beat_idx": 1}, {"start": 1.2, "end": 1.9, "beat_idx": 1}], {"0": Z, "2": Z})):
    def series(new):
        out = []; runs = zoom_runs(sc, ef)
        for k, s_ in enumerate(sc):
            e, off, dur = runs[k] if new else (ef.get(str(k), {}), 0, s_["end"] - s_["start"])
            for f in range(round((s_["end"] - s_["start"]) * 30)):
                t = f / 30 + off
                out.append(zoom_curve(t, dur, float(e.get("zoom") or 1), e.get("zoomMove", "in"), float(e.get("zoomIn") or 0)) if e.get("zoomIn") else float(e.get("zoom") or 1))
        return out
    def restarts(v):
        return sum(1 for a, b, c in zip(v, v[1:], v[2:]) if b < a - 1e-4 and c > b + 1e-4) + sum(1 for a, b in zip(v, v[1:]) if b < a - .05)
    print(f"[{name}] 다시 시작·튐 횟수: 고치기 전 {restarts(series(False))} / 고친 뒤 {restarts(series(True))}")
