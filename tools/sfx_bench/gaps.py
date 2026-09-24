# -*- coding: utf-8 -*-
import sys, numpy as np, soundfile as sf, glob, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SR=44100; HOP=int(0.005*SR); WIN=int(0.02*SR)
for d in sorted(glob.glob("sep/htdemucs/*")):
    vid=os.path.basename(d)
    x=sum(sf.read(f"{d}/{s}.wav")[0].mean(1) for s in ["drums","bass","other"])
    n=(len(x)-WIN)//HOP
    idx=np.arange(WIN)[None,:]+HOP*np.arange(n)[:,None]
    db=20*np.log10(np.sqrt((x[idx]**2).mean(1))+1e-9)
    on=db>-38; evs=[]; i=0
    while i<n:
        if on[i]:
            j=i
            while j<n and (on[j] or on[j:j+8].any()): j+=1
            evs.append((i,j)); i=j
        else: i+=1
    ts=[round(a*HOP/SR,2) for a,b in evs if (b-a)*HOP/SR>=0.015]
    print(f"{vid}  {len(ts)}발")
    if "우리" in vid: print("   ", ts)

print("\n--- 소리 없는 최장 구간(초) ---")
for d in sorted(glob.glob("sep/htdemucs/*")):
    vid=os.path.basename(d)
    x=sum(sf.read(f"{d}/{s}.wav")[0].mean(1) for s in ["drums","bass","other"])
    n=(len(x)-WIN)//HOP
    idx=np.arange(WIN)[None,:]+HOP*np.arange(n)[:,None]
    db=20*np.log10(np.sqrt((x[idx]**2).mean(1))+1e-9)
    on=db>-38; evs=[]; i=0
    while i<n:
        if on[i]:
            j=i
            while j<n and (on[j] or on[j:j+8].any()): j+=1
            evs.append((i,j)); i=j
        else: i+=1
    ts=[a*HOP/SR for a,b in evs if (b-a)*HOP/SR>=0.015]
    dur=len(x)/SR
    pts=[0.0]+ts+[dur]
    gaps=[round(pts[k+1]-pts[k],1) for k in range(len(pts)-1)]
    print(f"{vid:<18} 최장 {max(gaps):5.1f}s   평균간격 {dur/max(1,len(ts)):5.2f}s")
