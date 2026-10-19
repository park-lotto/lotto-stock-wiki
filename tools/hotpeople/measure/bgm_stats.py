# -*- coding: utf-8 -*-
"""BGM 리듬 실측 — BPM·온셋/분·컷↔비트 동기율(±80ms)·훅 구간(0~1s) 타격음 유무. librosa 필요(.venv).
표본 폴더에서: <프로젝트>\.venv\Scripts\python.exe ..\measure\bgm_stats.py → bgm.json + 콘솔
컷 시각은 rhythm.json(없으면 cuts.py 자와 같은 명령으로 재계산).
"""
import subprocess, json, glob, statistics as st, os
import numpy as np, librosa

rh = json.load(open("rhythm.json", encoding="utf-8")) if os.path.exists("rhythm.json") else {}


def cut_times(f):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vf", "crop=1080:790:0:483,select='gt(scene,0.3)',metadata=print:file=-", "-f", "null", "-"],
                       capture_output=True, text=True).stdout
    return [float(l.split("pts_time:")[1]) for l in r.splitlines() if "pts_time:" in l and float(l.split("pts_time:")[1]) > 0.2]


out = {}
for f in sorted(glob.glob("*.mp4")):
    vid = f[:11]
    wav = f"{vid}.tmp.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-ac", "1", "-ar", "22050", wav], check=True)
    y, sr = librosa.load(wav, sr=22050); os.remove(wav)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    bt = librosa.frames_to_time(beats, sr=sr)
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    ct = cut_times(f)
    sync = sum(1 for t in ct if len(bt) and np.min(np.abs(bt - t)) <= 0.08)
    out[vid] = {"bpm": round(float(np.atleast_1d(tempo)[0]), 1), "onset_per_min": round(len(on) / (len(y) / sr) * 60, 1),
                "cut_beat_sync": f"{sync}/{len(ct)}", "sync_pct": round(100 * sync / max(len(ct), 1)),
                "hit_in_first_1s": bool(len(on) and on[0] <= 1.0)}
    print(vid, out[vid])
json.dump(out, open("bgm.json", "w"), indent=1)
if out:
    v = list(out.values())
    print(f"\nBPM 중앙 {st.median([x['bpm'] for x in v])} · 온셋/분 중앙 {st.median([x['onset_per_min'] for x in v])} · 컷↔비트 동기 중앙 {st.median([x['sync_pct'] for x in v])}%")
