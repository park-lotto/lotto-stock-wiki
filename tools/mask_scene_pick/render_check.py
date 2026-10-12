"""관제 182 렌더 점검: 6장면 중 4~6번에만 빨간 가림효과 → 완성본 프레임 색 대조.
사용: ffmpeg 로 in.mp4(6초 회색 1080x1920) 만든 폴더를 인자로. PYTHONPATH=트랙 루트."""
import sys, pathlib, subprocess
from shopping_shorts import mix_pipeline, video_assemble
S = pathlib.Path(sys.argv[1])
cuts = [{"beat_idx": b, "fin": float(b), "dur": 1.0} for b in range(6)]
mix_pipeline.final_clip_pairs = lambda *a, **k: cuts
RED = {"l": 0, "t": 0, "w": 100, "h": 30, "kind": "box", "shape": "rect", "fx": "solid", "color": "#ff0000", "op": 100}
# 6장면 중 앞 3장면(훅) 빼고 4~6번(beat 3,4,5)에만
tpl = {"frame": {"masks": [dict(RED, scenes=[[3], [4], [5]])]}}
lays = mix_pipeline._scene_mask_layers(tpl, {}, [], [])
print("layers", [(l["start"], l["dur"]) for l in lays])
out = S / "out.mp4"; work = S / "w"; work.mkdir(exist_ok=True)
video_assemble._burn_captions(str(S / "in.mp4"), {"beats": []}, [], str(out), work,
                              deco={"scene_masks": lays}, skip_text=True)
for t in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1",
                          "-vf", "crop=10:10:500:100", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    print(f"t={t} 장면{int(t)+1} RGB={tuple(raw[:3])}")
