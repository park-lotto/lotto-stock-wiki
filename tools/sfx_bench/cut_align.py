# -*- coding: utf-8 -*-
import sys, subprocess, numpy as np, soundfile as sf
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SR=44100; HOP=int(0.005*SR); W=int(0.02*SR); TOL=0.15
for vid in ["2sUHI8hEafE","Iet-btoTSnU","tcaIPaGWLrE"]:
    d=f"sep/htdemucs/{vid}"
    x=sum(sf.read(f"{d}/{s}.wav")[0].mean(1) for s in ["drums","bass","other"])
    n=(len(x)-W)//HOP
    idx=np.arange(W)[None,:]+HOP*np.arange(n)[:,None]
    db=20*np.log10(np.sqrt((x[idx]**2).mean(1))+1e-9)
    on=db>-38; evs=[]; i=0
    while i<n:
        if on[i]:
            j=i
            while j<n and (on[j] or on[j:j+8].any()): j+=1
            evs.append(i*HOP/SR); i=j
        else: i+=1
    r=subprocess.run(["ffmpeg","-v","error","-i",vid+".mp4","-vf","select='gt(scene,0.30)',metadata=print:file=-","-an","-f","null","-"],capture_output=True,text=True)
    cuts=[float(l.split("pts_time:")[1].split()[0]) for l in r.stdout.splitlines() if "pts_time:" in l]
    hc=[c for c in cuts if any(abs(c-t)<=TOL for t in evs)]
    he=[t for t in evs if any(abs(c-t)<=TOL for c in cuts)]
    print(f"{vid:<14} 컷 {len(cuts):3d} · 효과음 {len(evs):3d} · 컷에 소리 {100*len(hc)/max(1,len(cuts)):3.0f}% · 소리가 컷 위 {100*len(he)/max(1,len(evs)):3.0f}%")
