# -*- coding: utf-8 -*-
"""샥탬스토리 채널 목소리 정하기 — 벤치 나레 성우 f0·말속도 vs 우리 성우 견본 f0 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/foreignshowshow/1편_STORMBAG/plan/voice_measure.py

f0 = 엔진 tools/calcopy/engine/audio_comp.pitch_stats(자기상관, 부르기만). 벤치 나레 구간 = C:/숏템_칼카피/foreignshowshow/asr/<id>.json
의 한국어 토막(나레만 받아쓴 파일 — 영어 원음 토막은 한글이 없어 빠진다). 벤치엔 BGM 이 깔려 있어 f0 가 조금 흔들릴 수 있다(분리 안 함).
결과 → plan/voice_measure.json
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine.audio_comp import pitch_stats  # noqa: E402
from shopping_shorts.channelkit.bench.constants import SR  # noqa: E402

BENCH = ["QMJtjJz4M6w", "vbxJ_v132ao", "kmQGQNJgSVo", "mVzrvBpMu3E"]   # 2jJoIbdciDY 는 받아쓰기 시각이 0~0.005초(깨짐)라 뺌
MP4 = "C:/숏템_칼카피/foreignshowshow/mp4/{}.mp4"
ASR = "C:/숏템_칼카피/foreignshowshow/asr/{}.json"
SAMPLES = ROOT / "shopping_shorts/assets/voice_samples"
VOICES = {  # 렌더러 TTS = 타입캐스트(tts_pause.synth). 미나(일레븐)는 참고로만.
    "필재": ("tc_68257f68bc6e3c161ab5078d", "tc-piljae-stable"), "김건": ("tc_61c2f7741330d213c238cba6", "tc-gunn-stable"),
    "박창수": ("tc_6059dad0b83880769a50502f", "tc-changsu-stable"), "용식이": ("tc_5feb2085cca1a479e73bac37", "tc-yongsik-stable"),
    "문정": ("tc_68f9c6a72f0f04a417bb136f", "tc-moonjung-stable"), "발키리": ("tc_60478557f12456064b353409", "tc-valkyrie-stable"),
    "지훈": ("tc_61f0859907085fc68561c9a1", "tc-jihoon-stable"), "유라(TC)": ("tc_61130d6cf89dd58a4c13295d", "tc-yura-stable"),
    "미나(일레븐·참고)": ("aiUUgjHa4mpHf6UenZuf", "kr-mina-stable"),
}


def pcm(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def nchar(s):
    return len(re.sub(r"[^0-9A-Za-z가-힣]", "", s))


def bench_one(vid):
    d = json.load(open(ASR.format(vid), encoding="utf-8"))
    segs = []
    for r in d.get("results", []):
        t = r["alternatives"][0]["content"]
        if re.search(r"[가-힣]", t) and float(r["end_time"]) - float(r["start_time"]) >= 1.0:   # 1초 미만 = 반응 번역(와우 등) 가능성 → 뺌
            segs.append({"start": float(r["start_time"]), "end": float(r["end_time"]), "text": t})
    x = pcm(MP4.format(vid))
    ps = pitch_stats(x, segs)
    secs = sum(s["end"] - s["start"] for s in segs)
    return {"id": vid, "segs": len(segs), "narr_sec": round(secs, 2), "chars": sum(nchar(s["text"]) for s in segs),
            "cps": round(sum(nchar(s["text"]) for s in segs) / secs, 2) if secs else None, **(ps or {"f0": "실패"})}


def voice_one(name):
    vid, fn = VOICES[name]
    x = pcm(SAMPLES / f"{fn}.mp3")
    ps = pitch_stats(x, [{"start": 0.0, "end": x.size / SR}])
    return {"name": name, "voice_id": vid, "sample": fn, **(ps or {"f0": "실패"})}


def main():
    B = [bench_one(v) for v in BENCH]
    V = [voice_one(n) for n in VOICES]
    f0s = [b["f0_median_hz"] for b in B if "f0_median_hz" in b]
    target = float(np.median(f0s))
    for v in V:
        if "f0_median_hz" in v:
            v["semitone_gap"] = float(round(abs(12 * np.log2(v["f0_median_hz"] / target)), 2))
    V.sort(key=lambda v: v.get("semitone_gap", 99))
    out = {"bench": B, "bench_f0_median_hz": round(target, 1), "voices": V}
    (Path(__file__).parent / "voice_measure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for b in B:
        print("벤치", b)
    for v in V:
        print("성우", v)


if __name__ == "__main__":
    main()
