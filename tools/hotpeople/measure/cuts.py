import subprocess, numpy as np, glob, json, statistics as st
out={}
for f in sorted(glob.glob("*.mp4")):
    if f.startswith("7PF"): continue
    dur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]).decode())
    # 슬롯 컷
    r=subprocess.run(["ffmpeg","-v","error","-i",f,"-vf","crop=1080:790:0:483,select='gt(scene,0.3)',metadata=print:file=-","-f","null","-"],capture_output=True,text=True).stdout
    cuts=[float(l.split("pts_time:")[1]) for l in r.splitlines() if "pts_time:" in l]
    cuts=[c for c in cuts if c>0.2]
    segs=[b-a for a,b in zip([0]+cuts,cuts+[dur])]
    # 자막 교체: 자막띠(1273~1470) 흑백 10fps, 프레임간 차이
    raw=subprocess.run(["ffmpeg","-v","error","-i",f,"-vf","fps=10,crop=1080:200:0:1272,scale=540:100","-f","rawvideo","-pix_fmt","gray","-"],capture_output=True).stdout
    n=len(raw)//54000; a=np.frombuffer(raw[:n*54000],np.uint8).reshape(n,100,540).astype(np.int16)
    ink=(a<100)
    diff=[(ink[i]^ink[i-1]).mean() for i in range(1,n)]
    ch=[ (i+1)/10 for i,d in enumerate(diff) if d>0.01]
    subs=[]; 
    for t in ch:
        if not subs or t-subs[-1]>0.4: subs.append(t)
    sdur=[b-a for a,b in zip([0]+subs,subs+[dur])]
    out[f]={"dur":dur,"cuts":len(cuts)+1,"cut_med":round(st.median(segs),2),"cut_min":round(min(segs),2),"cut_max":round(max(segs),2),
            "subs":len(subs)+1,"sub_med":round(st.median(sdur),2),"sub_times":subs}
    o=out[f]; print(f"{f[:11]} {dur:5.1f}s 컷 {o['cuts']:2d} (중앙 {o['cut_med']}s, {o['cut_min']}~{o['cut_max']}) | 자막 {o['subs']:2d} (중앙 {o['sub_med']}s)")
json.dump(out,open("cuts.json","w"))
