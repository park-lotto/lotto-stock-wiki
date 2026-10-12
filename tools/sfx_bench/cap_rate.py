# -*- coding: utf-8 -*-
"""이븐쇼핑 자막 교체 횟수 — 흰 바(세로 70~96, 180x320 기준) 글자 변화."""
import sys, subprocess, numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W,H=180,320
for vid in sys.argv[1:]:
    r=subprocess.run(["ffmpeg","-v","error","-i",vid+".mp4","-vf",f"fps=30,scale={W}:{H},format=gray","-f","rawvideo","-"],capture_output=True)
    f=np.frombuffer(r.stdout,np.uint8).reshape(-1,H,W).astype(float)
    txt=(f[:,70:96,6:174]<90).astype(float)
    d=np.abs(np.diff(txt,axis=0)).mean((1,2))
    ch=[];last=-9
    for i in np.where(d>0.04)[0]:
        t=(i+1)/30
        if t-last>0.2: ch.append(t)
        last=t
    dur=len(f)/30
    print(f"{vid:<14} 길이 {dur:5.1f}s · 자막 교체 {len(ch):3d}회 · 초당 {len(ch)/dur:.2f}")
