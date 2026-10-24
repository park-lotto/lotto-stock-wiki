# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/맛템썰템판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 옛 영상 재현용 읽기 전용 참고물 — 규칙은 판 칸·_pending.upgrade_from_hand_scripts 로 옮김)
"""yummyknow 3편 재렌더(TTS 재호출 0) — 줄 시작 받아쓰기(제미나이)는 매번 결과가 달라 원래 render/timeline.json 의 줄 시작을 그대로 쓴다 (관제 097, 10-17).
    PYTHONUTF8=1 py channel/yummyknow/rerender_맛템썰템.py <bread|ramyun|dubai>"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
Y = Path("C:/숏템_칼카피/yummyknow")
C = ROOT / "channel/yummyknow"
CFG = {
    "bread": ("새소재_rescene_bread", "새소재_rescene_bread", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "render/narr_full.mp3"),
    "ramyun": ("새소재_shinramyun_gumi", "새소재_shinramyun_gumi", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "render/narr_full.mp3"),
    "dubai": ("칼카피_rGFX", "칼카피_rGFX", "frame_rGFX_hook_맛템썰템.json", "frame_rGFX_body_맛템썰템.json", "tts/narr_full.mp3"),
}
folder, ydir, hk, bd, tts = CFG[sys.argv[1]]
tl = json.loads((Y / ydir / "render/timeline.json").read_text(encoding="utf-8"))
from tools.calcopy import narr_video
_S = json.loads((C / CFG[sys.argv[1]][0] / "대본.json").read_text(encoding="utf-8"))["final"]["lines"]
_st = narr_video.steps_of([l["text"] for l in _S], 10, "accumulate")
assert len(_st) == len(tl["steps"]), (len(_st), len(tl["steps"]))
starts = {}
for a, b in zip(_st, tl["steps"]):
    starts.setdefault(a["line"], b["t0"])
W = [starts[i] for i in sorted(starts)]
from tools.calcopy import narr_video
narr_video.line_starts = lambda audio, lines, segs, exp, log, asr, ask: list(W)
from tools.calcopy.engine import remake
d = C / folder
sys.argv = ["remake", str(Y / "engine_뜯기3/rGFXQlS9Cp4/뜯기.json"), str(d / bd), "--hook-frame", str(d / hk), "--materials", str(d / "재료.json"),
            "--script", str(d / "대본.json"), "--tts", str(Y / ydir / tts), "--out", str(Y / ydir / "render_맛템썰템")]
sys.exit(remake.main())
