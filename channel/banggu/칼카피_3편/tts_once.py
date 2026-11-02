# -*- coding: utf-8 -*-
"""방구석 3편 — 필재 TTS 1회(이미 있으면 다시 안 부름) → 쉼 줄임(narr_tight) → 효과음 시각을 자막 단계 시각으로 재료.json 에 채움.
    PYTHONUTF8=1 py channel/banggu/칼카피_3편/tts_once.py
1·2편과 같은 값: 필재(copy_render.NARR) · tempo 1.25 · 쉼 0.07초로 줄임 · 효과음 4발(훅 시작·훅 끝·핵심 공개·전개).
"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
D = Path(__file__).parent
R = Path("C:/숏템_칼카피/banggu/칼카피_3편/render")
R.mkdir(parents=True, exist_ok=True)
S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
lines = [l["text"] for l in S["final"]["lines"]]
full, tight = R / "narr_full.mp3", R / "narr_tight.mp3"
if not full.exists():   # ★타입캐스트는 딱 1회 — 파일이 있으면 절대 다시 부르지 않는다
    from shopping_shorts.channelkit import providers
    from tools.calcopy.copy_render import NARR
    providers.typecast_synth(NARR, tempo=1.25)(" ".join(lines), str(full))
    print("TTS 1회:", full)
if not tight.exists():
    f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
    mid = "silenceremove=stop_periods=-1:stop_duration=0.1:stop_threshold=-45dB:stop_silence=0.07"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(full), "-af", f"{f},areverse,{f},areverse,{mid}", "-c:a", "libmp3lame", "-q:a", "2", str(tight)],
                   check=True, stdin=subprocess.DEVNULL)
from tools.calcopy.narr_video import steps_of, time_steps
steps, dur = time_steps(steps_of(lines, 13, "accumulate"), str(tight))
first = {}
for s in steps:
    first.setdefault(s["sent"], s)
M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
t_of = {1: first[1]["t0"], 3: first[3]["t0"], 5: first[5]["t0"]}
M["sfx"][1]["t"] = round(t_of[1], 3)
M["sfx"][2]["t"] = round(t_of[3], 3)
M["sfx"][3]["t"] = round(t_of[5], 3)
for k in (1, 2, 3):
    M["sfx"][k]["why"] = M["sfx"][k]["why"].split(" — ")[0] + " — 쉼 줄인 TTS 자막 시각(narr_video.time_steps)"
(D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
print("narr_tight 길이", round(dur, 2), "효과음", [x["t"] for x in M["sfx"]])
