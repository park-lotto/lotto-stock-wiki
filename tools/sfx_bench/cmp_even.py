# -*- coding: utf-8 -*-
"""우리 완성본 vs 이븐쇼핑 — 같은 잣대로 효과음 횟수·크기 비교.
사용: py tools/sfx_bench/cmp_even.py <작업폴더>   (폴더 안 *.mp4 전부, sep/ 에 demucs 결과)
재는 것: 길이 / 효과음 건수 / 초당 건수 / 효과음 최대크기 중앙 / 목소리 중앙 / 대비(효과음-그순간목소리)
"""
import sys, os, glob, subprocess
import numpy as np, soundfile as sf
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SR = 44100; HOP = int(0.005*SR); WIN = int(0.02*SR); THR = -38.0
work = sys.argv[1]; os.chdir(work)
mp4s = sorted(glob.glob("*.mp4"))
os.makedirs("wav", exist_ok=True)
for m in mp4s:
    w = "wav/" + os.path.splitext(m)[0] + ".wav"
    if not os.path.exists(w):
        subprocess.run(["ffmpeg","-v","error","-y","-i",m,"-ac","2","-ar",str(SR),w], check=True)
need = [w for w in sorted(glob.glob("wav/*.wav"))
        if not os.path.exists("sep/htdemucs/"+os.path.splitext(os.path.basename(w))[0]+"/vocals.wav")]
if need:
    subprocess.run([sys.executable,"-m","demucs","-n","htdemucs","-o","sep"]+need, check=True)
print(f"{'영상':<16}{'길이':>6}{'건수':>6}{'초당':>7}{'효과음최대중앙':>16}{'목소리중앙':>12}{'대비중앙':>10}{'묻힘<3dB':>10}")
for d in sorted(glob.glob("sep/htdemucs/*")):
    vid = os.path.basename(d)
    x = sum(sf.read(f"{d}/{s}.wav")[0].mean(1) for s in ["drums","bass","other"])
    v = sf.read(f"{d}/vocals.wav")[0].mean(1)
    n = (len(x)-WIN)//HOP
    idx = np.arange(WIN)[None,:] + HOP*np.arange(n)[:,None]
    db = 20*np.log10(np.sqrt((x[idx]**2).mean(1))+1e-9)
    on = db > THR
    evs = []; i = 0
    while i < n:
        if on[i]:
            j = i
            while j < n and (on[j] or on[j:j+8].any()): j += 1
            evs.append((i,j)); i = j
        else: i += 1
    peaks, contrasts = [], []
    for a,b in evs:
        if (b-a)*HOP/SR < 0.015: continue
        pk = float(db[a:b].max())
        c = int(a*HOP); lo = max(0, c-int(0.15*SR)); hi = min(len(v), c+int(0.15*SR))
        vr = 20*np.log10(np.sqrt((v[lo:hi]**2).mean())+1e-9)
        peaks.append(pk); contrasts.append(pk-vr)
    dur = len(x)/SR
    vmed = float(np.median(20*np.log10(np.sqrt((v[:len(v)//int(0.05*SR)*int(0.05*SR)].reshape(-1,int(0.05*SR))**2).mean(1))+1e-9)))
    if not peaks: print(f"{vid:<16}{dur:6.1f}{0:6d}"); continue
    buried = sum(1 for c in contrasts if c < 3.0)
    print(f"{vid:<16}{dur:6.1f}{len(peaks):6d}{len(peaks)/dur:7.2f}{np.median(peaks):16.1f}{vmed:12.1f}{np.median(contrasts):10.1f}{buried:6d}/{len(peaks):<4d}")
