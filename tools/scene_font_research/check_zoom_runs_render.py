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

runs = zoom_runs(sc, ef)
A = part(runs[0][0], 0, .8, round(runs[0][2] * 30), 0, "A")
old_B = part({}, .8, 1.9, 33, 0, "oldB")
new_B = part(runs[1][0], .8, 1.9, round(runs[1][2] * 30), round(runs[1][1] * 30), "newB")
inner = np.mean([diff(A[k], A[k + 1]) for k in range(len(A) - 1)])
print(f"칸 안 프레임 간 평균 차이 {inner:.1f}")
print(f"경계 차이: 고치기 전 {diff(A[-1], old_B[0]):.1f} / 고친 뒤 {diff(A[-1], new_B[0]):.1f}")
