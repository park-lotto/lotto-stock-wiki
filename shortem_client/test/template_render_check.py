# -*- coding: utf-8 -*-
"""숏템메이커 템플릿을 고른 팩이 **완성본 합성 경로**(scene_style.compose — remake_video·narr_video 가 부르는 그 함수)까지 가나(관제 234 5판).

    py test/template_render_check.py <엔진 폴더> <프리셋 경로> <mode> <템플릿 id> <출력 폴더>
같은 팩(템플릿 있음/없음)으로 merge_preset_pack → to_snapshot → compose 를 진짜로 돌려 final.mp4 를 만들고,
첫 장면 1초 프레임을 뽑아 둘이 실제로 다른지(템플릿이 먹었나) + 렌더 레이어(render_layer_one) 경로도 같은 템플릿인지 잰다.
출력 JSON {with, without, diff_ratio, layer_vs_final}
"""
import json
import pathlib
import subprocess
import sys

eng = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(eng))
import numpy as np  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402
from shopping_shorts import calcopy_make as MK, scene_style  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from tools.calcopy.remake_video import title_text  # noqa: E402
from tools.calcopy import preview_request as PR  # noqa: E402

preset, mode, tid, out = sys.argv[2], sys.argv[3], sys.argv[4], pathlib.Path(sys.argv[5]).resolve()
out.mkdir(parents=True, exist_ok=True)
mat = out / "material.mp4"
if not mat.exists():   # 재료 대신 시험 영상(색 막대) 12초 + 무음
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1080:r=30:d=12", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", "12", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(mat)], check=True)
tl = PR._sample_timeline(PR.SAMPLE_LINES)
res = {}
for name, pack in (("with", {"template": {"mode": mode, "id": tid}, "brand": {"channel_name": "우리채널"}}), ("without", {"brand": {"channel_name": "우리채널"}})):
    cfg = MK.merge_preset_pack(preset, pack)
    spec = schema.validate(cfg["frame"])
    head = {"text": title_text(spec, {"title": PR.SAMPLE_TITLE})}
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(cfg["frame"]))
    final = out / f"final_{name}.mp4"
    scene_style.compose(str(mat), tl, snap, str(final), out / f"work_{name}", head)
    png = out / f"final_{name}_1s.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(final), "-frames:v", "1", str(png)], check=True)
    layer = scene_style.render_layer_one(tl, snap, out / f"layer_{name}", 0, head)
    res[name] = {"final": str(final), "frame": str(png), "layer": str(layer), "presetId": snap["presetId"]}
a, b = (np.asarray(Image.open(res[k]["frame"]).convert("RGB").resize((540, 960))).astype(int) for k in ("with", "without"))
res["diff_ratio"] = round(float((np.abs(a - b).max(axis=2) > 40).mean()), 4)
print(json.dumps(res, ensure_ascii=False))
