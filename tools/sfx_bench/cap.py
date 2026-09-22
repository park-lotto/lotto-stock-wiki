import json,sys,subprocess,numpy as np
sys.stdout.reconfigure(encoding="utf-8")
p=json.load(open("prep.json",encoding="utf-8"))
W,H=180,320
out={}
for vid in p:
    r=subprocess.run(["ffmpeg","-v","error","-i",f"{vid}.mp4","-vf",f"fps=30,scale={W}:{H},format=gray","-f","rawvideo","-"],capture_output=True)
    f=np.frombuffer(r.stdout,np.uint8).reshape(-1,H,W).astype(float)
    cap=f[:,70:96,6:174]            # 자막 줄 칸
    txt=(cap<90).astype(float)        # 검은 글자 픽셀
    d=np.abs(np.diff(txt,axis=0)).mean((1,2))
    ch=[];last=-9
    for i in np.where(d>0.04)[0]:
        t=(i+1)/30
        if t-last>0.2: ch.append(round(t,3))
        last=t
    out[vid]=ch
    print(vid,"자막바뀜",len(ch),"문장수",len(p[vid]["segs"]))
json.dump(out,open("capchg.json","w"),indent=0)
