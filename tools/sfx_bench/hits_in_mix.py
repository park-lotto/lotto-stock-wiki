# -*- coding: utf-8 -*-
import sys, json, subprocess, numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SR=44100
def load(p):
    r=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True)
    return np.frombuffer(r.stdout,np.float32).astype(float)
x=load("라이브렌더.mp4")
try: nv=__import__("soundfile").read("sep/htdemucs/라이브렌더/other.wav")[0]
except Exception: nv=None
ev=json.load(open("ev_bb38.json",encoding="utf-8"))
print("완성본 %.1fs · 계획 %d발"%(len(x)/SR,len(ev)))
print(f"{'시각':>6} {'소리':<10}{'섞인소리최대':>12}{'직전0.3초':>10}{'솟음':>7}  판정")
bad=0
for t,name,g in ev:
    a=int(t*SR); b=min(len(x),a+int(0.25*SR)); lo=max(0,a-int(0.30*SR))
    if a>=len(x): print(f"{t:6.2f} {name:<10}  영상 밖"); bad+=1; continue
    pk=20*np.log10(np.abs(x[a:b]).max()+1e-9)
    base=20*np.log10(np.sqrt((x[lo:a]**2).mean())+1e-9)
    r=pk-base
    m="들림" if r>=6 else ("약함" if r>=3 else "묻힘")
    if r<6: bad+=1
    print(f"{t:6.2f} {name:<10}{pk:12.1f}{base:10.1f}{r:7.1f}  {m}")
print("6dB 미만 %d/%d"%(bad,len(ev)))
