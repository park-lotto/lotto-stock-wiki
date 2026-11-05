# -*- coding: utf-8 -*-
"""소리 실측 — 통합 LUFS·트루피크·LRA·단기폭(p90−p10)·오프닝 3초 vs 본편 순간음량.
표본 mp4 폴더에서: PYTHONUTF8=1 py ../measure/audio.py → audio.json
자 정의는 볼케이노 measure_peak/measure_lufs_spread와 같다(마지막 I:/Peak: 값, S: −70 이하 제외, 20개 미만 None).
"""
import subprocess, re, glob, json, statistics as st

out = {}
for f in sorted(glob.glob("*.mp4")):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", f, "-af", "ebur128=peak=true:framelog=info", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    I = re.findall(r"^\s*I:\s*(-?[\d.]+) LUFS", r, re.M)
    TP = re.findall(r"Peak:\s*(-?[\d.]+) dBFS", r)
    LRA = re.findall(r"LRA:\s*(-?[\d.]+) LU", r)
    S = sorted(float(x) for x in re.findall(r"S:\s*(-?[\d.]+)", r) if float(x) > -70)
    spread = (S[int(len(S) * .9)] - S[int(len(S) * .1)]) if len(S) >= 20 else None
    M = re.findall(r"t:\s*([\d.]+)\s+.*?M:\s*(-?[\d.]+)", r)
    m3 = [float(m) for t, m in M if float(t) <= 3 and float(m) > -70]
    mr = [float(m) for t, m in M if float(t) > 3 and float(m) > -70]
    out[f[:11]] = {"I": float(I[-1]) if I else None, "TP": float(TP[-1]) if TP else None,
                   "LRA": float(LRA[-1]) if LRA else None, "S_spread": round(spread, 1) if spread is not None else None,
                   "open3s_M": round(st.median(m3), 1) if m3 else None, "rest_M": round(st.median(mr), 1) if mr else None}
    print(f[:11], out[f[:11]])
json.dump(out, open("audio.json", "w"), indent=1)
Is = [v["I"] for v in out.values() if v["I"] is not None]
print("I 중앙", st.median(Is), "범위", min(Is), max(Is))
