# -*- coding: utf-8 -*-
"""핫템 편 외관만 바꿔 재렌더(10-17): 채널명 숏템리폿·하늘 글로우·제목 흰/주황·강조 자막 노랑. 나레(TTS) 파일은 기존 것 복사(재호출 없음).
usage: py make_render_숏템리폿.py oe11|robot   — 원본 대본/재료/frame 은 건드리지 않고 복사본에서 돌린다. 로봇폰은 make_render.py 를 불러 경로만 바꿔 쓴다."""
import importlib.util, json, os, shutil, sys
from pathlib import Path
H = Path(__file__).resolve().parent
ROOT = H.parents[1]
sys.path.insert(0, str(ROOT))
YEL = [205, 170, 110]
which = sys.argv[1]

from tools.calcopy import narr_video as _nv0


def _emph_box(text, cap, rgb, dst, dy=0):
    """강조 자막 v2: 틀 자막과 같은 박스 + 노랑 글자 + 노랑 밑줄(원본 '색만 바꾼 외곽선 글자'와 다른 꼴)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(_nv0._font_file(cap["font"]), int(round(cap["size"])))
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    cx, cy = cap["x"], cap["y"] + cap["line_h"] / 2 + dy
    l, t, r, b = dr.textbbox((cx, cy), text, font=font, anchor="mm")
    bx = cap.get("box") or {"rgb": (18, 27, 52), "pad": 20, "radius": 14}; pad = bx["pad"]
    dr.rounded_rectangle([l - pad, t - pad, r + pad, b + pad], radius=bx["radius"], fill=tuple(bx["rgb"]) + (255,))
    dr.text((cx, cy), text, font=font, fill=tuple(int(v) for v in rgb) + (255,), anchor="mm")
    dr.rectangle([l, b + 6, r, b + 9], fill=tuple(int(v) for v in rgb) + (255,))
    im.save(dst)
    return Path(dst)


_nv0.emph_png = _emph_box
base = H / ("칼카피_OE11" if which == "oe11" else "칼카피_로봇폰")
OLD = Path("C:/숏템_칼카피/hottemreport") / base.name / "make"
NEW = Path("C:/숏템_칼카피/hottemreport/숏템리폿") / which
IN, MK = NEW / "in", NEW / "make"
IN.mkdir(parents=True, exist_ok=True); MK.mkdir(parents=True, exist_ok=True)
S = json.loads((base / "대본.json").read_text(encoding="utf-8"))
for e in S["caption_events"]:
    if e.get("kind") == "emph":
        e["rgb"] = YEL
(IN / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
shutil.copy(base / "재료.json", IN / "재료.json")
shutil.copy(base / "frame_숏템리폿.json", IN / "frame_숏템리폿.json")
for f in ("narr_full.mp3", "narr_full_t106.wav", "narr_gapped.wav", "narr_gapped_t106.wav"):
    if (OLD / f).exists() and not (MK / f).exists():
        shutil.copy(OLD / f, MK / f)

if which == "robot":
    spec = importlib.util.spec_from_file_location("mr", base / "make_render.py")
    mr = importlib.util.module_from_spec(spec); spec.loader.exec_module(mr)
    mr.D = IN; mr.MK = MK; mr.TTS_RAW = MK / "narr_full.mp3"; mr.TTS = MK / "narr_full_t106.wav"; mr.WAV = MK / "narr_gapped_t106.wav"
    os.environ["HR_FRAME"] = "frame_숏템리폿.json"; mr.OUTNAME = "final_숏템리폿.mp4"
    mr.main(render="--dry" not in sys.argv)
else:
    from tools.calcopy import narr_video as nv, hottem_audio as ha
    plan = {"tteutgi": str(H / "칼카피_OE11/뜯기2/뜯기.json"),
            "frames": [{"frame": str(IN / "frame_숏템리폿.json"), "t_end": None}], "script": str(IN / "대본.json"),
            "tts": str(MK / "narr_gapped.wav"), "materials": str(IN / "재료.json"), "out": str(MK),
            "bgm": "passo_bem_solto", "bgm_ratio": 0.15, "lufs": -15.3, "chunk": 10, "caption_mode": "replace"}
    # 컷·자막 시각은 통과본(timeline.json) 그대로 고정 — 엔진이 그 뒤 바뀌어(받아쓰기 빈 답 폴백) 시각이 흔들리는 것을 막는다
    _old = json.loads((OLD / "timeline.json").read_text(encoding="utf-8"))["steps"]
    nv.time_steps = lambda st, audio, snap=0.4, **kw: ([dict(s) for s in _old], nv.speech_segments(audio)[1])
    print("final", nv.build(plan))
    res = ha.add_source_bed(str(MK / "final.mp4"), str(MK / "timeline.json"), str(IN / "재료.json"), str(MK / "narr_gapped.wav"),
                            str(MK / "final_숏템리폿.mp4"), 1.0, 10.0, work=str(MK / "srcbed"), gap_gain=[[3.49, 6.09, 8.7], [8.76, 13.76, 6.5]])
    print(json.dumps(res, ensure_ascii=False))
