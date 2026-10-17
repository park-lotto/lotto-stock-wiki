# -*- coding: utf-8 -*-
"""맛템썰템 v2 — 그림 칸을 큰 창 전체(가로 1080·창 높이 cover)로 감싸 재렌더(TTS 0). 옛 엔진 복사본(scratch eng_*)의 tools 로 실행.
   cwd=엔진 복사본 루트:  PYTHONPATH=<repo> py <이 파일> <bread|ramyun|dubai>"""
import inspect, json, runpy, sys
from pathlib import Path
import os
REAL = Path(os.environ["REAL"])
Y = Path("C:/숏템_칼카피/yummyknow")
key = sys.argv[1]
D = REAL / "channel/yummyknow"
CFG = {"bread": ("새소재_rescene_bread", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "render/narr_full.mp3"),
       "ramyun": ("새소재_shinramyun_gumi", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "render/narr_full.mp3"),
       "dubai": ("칼카피_rGFX", "frame_rGFX_hook_맛템썰템.json", "frame_rGFX_body_맛템썰템.json", "tts/narr_full.mp3")}
folder, hk, bd, tts = CFG[key]
from tools.calcopy import narr_video as nv
_orig = nv.shot_clip
def _wide(*a, **k):
    b = inspect.signature(_orig).bind(*a, **k); b.apply_defaults(); g = b.arguments
    if not g["full"]:
        g["box"] = [48, 0, g["win"]["w"] - 96, g["win"]["h"]]; g["min_y"] = 0; g["anchor"] = True; g["fit"] = "cover"
    return _orig(*b.args, **b.kwargs)
nv.shot_clip = _wide
out = Y / folder / "render_맛템썰템_E"
if key == "dubai":
    plan = json.loads((D / folder / "plan_맛템썰템.json").read_text(encoding="utf-8"))
    plan["out"] = str(out)
    plan["frames"] = [{"frame": str(D / folder / hk), "t_end": None}, {"frame": str(D / folder / bd), "t_end": None}]
    print("final", nv.build(plan))
else:
    sys.argv = ["remake", str(Y / "engine_뜯기3/rGFXQlS9Cp4/뜯기.json"), str(D / folder / bd), "--hook-frame", str(D / folder / hk),
                "--materials", str(D / folder / "재료.json"), "--script", str(D / folder / "대본.json"), "--tts", str(Y / folder / tts), "--out", str(out)]
    from tools.calcopy.engine import remake
    sys.exit(remake.main())
