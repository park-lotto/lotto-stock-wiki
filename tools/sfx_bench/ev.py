import soundfile as sf, numpy as np, glob, os, sys, json
sys.stdout.reconfigure(encoding="utf-8")
SR=44100; HOP=int(0.005*SR); WIN=int(0.02*SR)
prep=json.load(open("prep.json",encoding="utf-8"))
allev={}
for d in sorted(glob.glob("sep/htdemucs/*")):
    vid=os.path.basename(d)
    x=sf.read(f"{d}/nv.wav")[0]; v=sf.read(f"{d}/vocals.wav")[0].mean(1)
    n=(len(x)-WIN)//HOP
    idx=np.arange(WIN)[None,:]+HOP*np.arange(n)[:,None]
    db=20*np.log10(np.sqrt((x[idx]**2).mean(1))+1e-9)
    on=db>-38
    # merge gaps <40ms
    evs=[];i=0
    while i<n:
        if on[i]:
            j=i
            while j<n and (on[j] or on[j:j+8].any()): j+=1
            evs.append((i,j)); i=j
        else: i+=1
    out=[]
    for a,b in evs:
        s=a*HOP/SR; e=(b*HOP+WIN)/SR
        if e-s<0.015: continue
        seg=x[a*HOP:b*HOP+WIN]
        sp=np.abs(np.fft.rfft(seg*np.hanning(len(seg)))); f=np.fft.rfftfreq(len(seg),1/SR)
        cen=float((sp*f).sum()/sp.sum())
        out.append({"s":round(s,3),"e":round(e,3),"dur":round(e-s,3),"peak":round(float(db[a:b].max()),1),"cen":round(cen)})
    allev[vid]=out
    # vocal leakage check: vocal rms outside whisper segments
    segs=prep[vid]["segs"]; t=np.arange(len(v))/SR
    mask=np.ones(len(v),bool)
    for sg in segs: mask[int(sg["s"]*SR):int(sg["e"]*SR)]=False
    gap=v[mask]
    gdb=20*np.log10(np.sqrt((gap**2).mean())+1e-9) if gap.size else None
    print(vid,"사건",len(out),"길이중앙",np.median([o["dur"] for o in out]) if out else 0,"| 대사 밖 목소리층",round(gdb,1) if gdb else "-")
json.dump(allev,open("events.json","w"),indent=0)
