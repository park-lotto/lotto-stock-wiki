import subprocess, sys, numpy as np, glob, json
W,H=1080,1920
res={}
for f in sorted(glob.glob("*.mp4")):
    dur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]).decode())
    frames=[]
    for i in range(24):
        t=0.5+i*(dur-1)/24
        raw=subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.2f}","-i",f,"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
        if len(raw)==W*H*3: frames.append(np.frombuffer(raw,np.uint8).reshape(H,W,3))
    a=np.stack(frames).astype(np.int16)
    nonwhite=(a.min(axis=3)<200).mean(axis=(0,2))          # 행별 비흰색 비율(평균)
    tstd=a.mean(axis=3).std(axis=0).mean(axis=1)           # 행별 시간 변화량
    # 슬롯 = 비흰색 비율 > 0.6 인 가장 긴 연속 구간
    m=nonwhite>0.6; best=(0,0); s=None
    for y in range(H+1):
        if y<H and m[y]:
            s=y if s is None else s
        elif s is not None:
            if y-s>best[1]-best[0]: best=(s,y)
            s=None
    # 슬롯 좌우: 슬롯 가운데 행들에서 비흰색 열
    ys=slice(best[0]+20,best[1]-20)
    colnw=(a[:,ys].min(axis=3)<200).mean(axis=(0,1))
    xs=np.where(colnw>0.5)[0]
    # 텍스트 띠: 슬롯 위/아래에서 비흰색이 있는 행 구간들
    def bands(lo,hi):
        out=[];s=None
        for y in range(lo,hi+1):
            on = y<hi and nonwhite[y]>0.004
            if on and s is None: s=y
            if not on and s is not None:
                if y-s>=6: out.append((s,y))
                s=None
        return out
    res[f]={"slot_y":best,"slot_x":(int(xs.min()),int(xs.max())+1) if len(xs) else None,
            "above":bands(0,best[0]),"below":bands(best[1],H)}
    print(f, json.dumps(res[f]))
json.dump(res,open("rows.json","w"))
