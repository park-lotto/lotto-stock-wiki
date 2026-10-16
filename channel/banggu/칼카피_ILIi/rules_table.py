# -*- coding: utf-8 -*-
"""ILIi 렌더 뒤 규칙표(원본 뜯기2 실측 vs 우리 완성본 실측) — 말속도·쉼·덕킹·LUFS·컷·자막·재료 시간 비율·효과음.
    PYTHONUTF8=1 py channel/banggu/칼카피_ILIi/rules_table.py <render 폴더>
덕킹 = 나레 말 구간 RMS − 말 없는 구간(쉼) RMS (뜯기 audio_comp.duck_db 와 같은 뜻 — 섞인 소리에서 잼)."""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.narr_video import speech_segments
R = Path(sys.argv[1]); D = Path(__file__).parent
J = json.loads((D / "뜯기2/뜯기.json").read_text(encoding="utf-8"))
S = json.loads((D / "대본.json").read_text(encoding="utf-8")); M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
A = json.loads((R / "audio.json").read_text(encoding="utf-8")); T = json.loads((R / "timeline.json").read_text(encoding="utf-8"))
final = R / "final.mp4"

def pcm(p):
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(b, np.int16).astype(np.float32) / 32768

def db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)

segs, dur = speech_segments(A["tts"])   # 렌더에 실제로 쓴 나레 파일(audio.json)
chars = sum(len(l["text"].replace(" ", "").replace(",", "")) for l in S["final"]["lines"])
speech = sum(b - a for a, b in segs)
gaps = [b2 - a1 for (_, a1), (b2, _) in zip(segs, segs[1:])]
x = pcm(final); sr = 16000
mask = np.zeros(len(x), bool)
for a, b in segs: mask[int(a * sr):int(b * sr)] = True
duck = round(db(x[mask]) - db(x[~mask]), 1) if (~mask).sum() > sr * 0.2 else None
shots = T["shots"]; lens = [b - a for a, b in shots]
kind_t = {}
for (a, b), s in zip(shots, M["shots"]):
    kind_t[s["kind"]] = kind_t.get(s["kind"], 0) + (b - a)
tot = sum(kind_t.values())
au = J["audio"]; comp = au["composition"]; tr = au["transcript"]
caps = [s for s in T["steps"]]
rows = [
 ("길이(초)", J["probe"]["duration"], round(T["dur"], 2)),
 ("말속도(자/초, 공백 제외, 말 구간 기준)", tr.get("cps"), round(chars / speech, 2)),
 ("말속도(자/초, 전체 길이 기준)", round(tr.get("chars_nospace_ko", 0) / J["probe"]["duration"], 2), round(chars / dur, 2)),
 ("말 차지 비율", tr.get("speech_share_ko"), round(speech / dur, 3)),
 ("쉼 수(≥0.12초) · 중앙(초)", f"{len(tr.get('pauses') or [])} · {tr.get('pause_median')}", f"{len(gaps)} · {round(float(np.median(gaps)), 2) if gaps else None}"),
 ("덕킹 dB(말 − 쉼)", comp.get("duck_db"), duck),
 ("LUFS(I)", au["bench"].get("I"), A["final"].get("I")),
 ("컷 수 · 첫 컷(초)", f"{len(J['cuts']['times']) + 1} · {J['cuts']['first_cut']}", f"{len(shots)} · {round(shots[1][0], 2)}"),
 ("컷 길이 중앙(초)", J["cuts"]["shot_len"].get("median") if isinstance(J["cuts"].get("shot_len"), dict) else J["cuts"].get("shot_len"), round(float(np.median(lens)), 2)),
 ("자막 상태 수(누적 단계)", J["captions"]["n_spans"], len([c for c in caps if c["t0"] >= T["hook_end"] - 1e-6])),
 ("자막당 초", round((J["probe"]["duration"] - 1.63) / max(1, J["captions"]["n_spans"]), 2), round((T["dur"] - T["hook_end"]) / max(1, len([c for c in caps if c["t0"] >= T["hook_end"] - 1e-6])), 2)),
 ("훅 카드 길이(초)", 1.633, round(T["hook_end"], 2)),
 ("재료 시간 비율", "남의영상재편집 1.0(1판 판독) · 짤 1개 6.0~8.4초", {k: round(v / tot, 2) for k, v in kind_t.items()}),
 ("효과음(발)", f"{len((au.get('asr_extra') or {}).get('sfx') or [])} (받아쓰기 귀) / 솟음 {comp.get('sfx', {}).get('times') if isinstance(comp.get('sfx'), dict) else '-'}", [round(s[1], 2) for s in A["sfx"]]),
]
md = ["# 규칙표 — ILIi 원본 vs 우리 완성본", "", "| 항목 | 원본(뜯기2) | 우리(final.mp4) |", "|---|---|---|"]
md += [f"| {a} | {b} | {c} |" for a, b, c in rows]
md += ["", f"- 나레: 타입캐스트 필재 tempo 1.25 · 파일 {Path(A['tts']).name} · 길이 {dur:.2f}초 · 말 구간 {len(segs)}개", f"- BGM {A.get('bgm')} ratio {A.get('bgm_ratio')} · 목표 LUFS {A.get('target_lufs')}"]
(R / "규칙표.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md))
