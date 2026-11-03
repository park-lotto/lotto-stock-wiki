# -*- coding: utf-8 -*-
"""설정 화면 미리보기 = 완성본 렌더인가(관제 234 5판) — 같은 팩·같은 장면을 공식 렌더 경로(scene_style.render_layer_one)로 찍어
화면 캡처(1080×1920)와 겹쳐 잰다. 렌더 레이어는 투명 바탕이라 검정 위에 얹어 비교한다(화면의 폰 바탕이 검정).

    py test/ui_vs_render.py <엔진 폴더> <프리셋 경로> <팩.json> <장면 번호> <화면.png> <출력 폴더>
출력: JSON {mean_abs, diff_ratio, ui_ink, render_ink} — diff_ratio = 차이 24 넘는 점 비율(글자 안티에일리어싱 정도는 허용)
"""
import json
import pathlib
import sys

eng = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(eng))
from PIL import Image, ImageChops  # noqa: E402
import numpy as np  # noqa: E402
from shopping_shorts import calcopy_make as MK, scene_style  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from tools.calcopy.remake_video import title_text  # noqa: E402
from tools.calcopy import preview_request as PR  # noqa: E402

preset, pack, idx, ui_png, out = sys.argv[2], json.loads(pathlib.Path(sys.argv[3]).read_text(encoding="utf-8")), int(sys.argv[4]), sys.argv[5], pathlib.Path(sys.argv[6])
cfg = MK.merge_preset_pack(preset, pack)
spec = schema.validate(cfg["frame"])
tl = PR._sample_timeline(PR.SAMPLE_LINES)
head = {"text": title_text(spec, {"title": PR.SAMPLE_TITLE})}
snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(cfg["frame"]))
layer = scene_style.render_layer_one(tl, snap, out, idx, head)
ren = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
ren.alpha_composite(Image.open(layer).convert("RGBA").resize((1080, 1920)))
ren = ren.convert("RGB")
ren.save(out / "render_on_black.png")
ui = Image.open(ui_png).convert("RGB").resize((1080, 1920))
d = np.asarray(ImageChops.difference(ui, ren)).max(axis=2)
ink = lambda im: float((np.asarray(im).max(axis=2) > 40).mean())
Image.fromarray(((d > 24) * 255).astype("uint8")).save(out / "diff.png")
print(json.dumps({"mean_abs": round(float(d.mean()), 3), "diff_ratio": round(float((d > 24).mean()), 5),
                  "ui_ink": round(ink(ui), 4), "render_ink": round(ink(ren), 4), "render": str(out / "render_on_black.png")}))
