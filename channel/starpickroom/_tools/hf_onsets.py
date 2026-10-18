# -*- coding: utf-8 -*-
"""효과음 자리 어림 — 4~12kHz 띠 에너지의 순간 솟음(앞 0.3초 중앙값 대비 +9dB) 시각. 귀 대신 쓰는 보조 지표(관제 097).
    PYTHONUTF8=1 py channel/starpickroom/_tools/hf_onsets.py <mp4> [t0 t1]"""
import subprocess, sys, numpy as np
mp4 = sys.argv[1]; SR = 32000
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, np.float32); hop = 320; win = 1024
fr = [x[i:i + win] * np.hanning(win) for i in range(0, len(x) - win, hop)]
S = np.abs(np.fft.rfft(np.array(fr), axis=1)); f = np.fft.rfftfreq(win, 1 / SR)
hf = 10 * np.log10(S[:, (f > 4000) & (f < 12000)].sum(1) ** 2 + 1e-9); full = 10 * np.log10((S ** 2).sum(1) + 1e-9)
t = np.arange(len(hf)) * hop / SR; out = []; last = -1
for i in range(30, len(hf)):
    base = np.median(hf[i - 30:i])
    if hf[i] - base > 9 and t[i] - last > 0.25:
        out.append((round(float(t[i]), 2), round(float(hf[i] - base), 1))); last = t[i]
a, b = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (0, 1e9)
print(len([o for o in out if a <= o[0] <= b]), [o for o in out if a <= o[0] <= b])
