# 검정 상자 모서리 반지름 직접 재기: 똑바른 상자(기울기 |a|<1)의 위·아래 줄마다 왼/오 끝 들어감 → 원 맞추기
import json, subprocess, numpy as np, cv2
SRC = "C:/t/kal_snap/data/snapbwatni/src/{}.mp4"
d = json.load(open("C:/t/audit_snap2/bubble_measure_re.json", encoding="utf-8"))
def frame(v, t):
    r = subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.2f}","-i",SRC.format(v),"-frames:v","1","-f","rawvideo","-pix_fmt","bgr24","-"],capture_output=True)
    return np.frombuffer(r.stdout,np.uint8).reshape(1920,1080,3)
def fit_r(prof):   # prof[y]=들어감(px), y=0 이 상자 끝줄
    best=None
    for r in np.arange(3,80,0.5):
        ys=np.arange(len(prof)); m=ys<r
        if m.sum()<3: continue
        pred=r-np.sqrt(np.maximum(0,r*r-(r-ys[m]-0.5)**2))
        e=np.median(np.abs(pred-prof[m]))
        if best is None or e<best[1]: best=(r,e)
    return best
out=[]
for x in d:
    if "radius" not in x or abs(x.get("box_angle",9))>1.0: continue
    im=frame(x["id"],x["t"]); cx,cy,bw,bh=x["box_cx"],x["box_cy"],x["box_w"],x["box_h"]
    y0,y1=max(0,cy-bh//2-30),min(1920,cy+bh//2+30); x0,x1=max(0,cx-bw//2-30),min(1080,cx+bw//2+30)
    c=im[y0:y1,x0:x1]; dark=(c.max(2)<45).astype(np.uint8)
    n,lab,st,_=cv2.connectedComponentsWithStats(cv2.morphologyEx(dark,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8)),8)
    k=1+int(np.argmax(st[1:,4])); m=(lab==k)
    m=cv2.morphologyEx(m.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((25,25),np.uint8))>0
    rows=np.where(m.any(1))[0]; cols=np.where(m.any(0))[0]
    L,R,T,B=cols[0],cols[-1],rows[0],rows[-1]
    res=[]
    for top in (True,False):
        rr=range(T,T+60) if top else range(B,B-60,-1)
        for left in (True,False):
            prof=[]
            for y in rr:
                xs=np.where(m[y])[0]
                if not len(xs): prof.append(60); continue
                prof.append((xs[0]-L) if left else (R-xs[-1]))
            f=fit_r(np.array(prof,float))
            if f: res.append(round(float(f[0]),1))
    cv2.imwrite(f"C:/t/fm_jev/bub/{x['id']}_{x['t']}.png", c)
    out.append({"id":x["id"],"t":x["t"],"area_r":x["radius"],"fill":x["box_fill"],"h":int(B-T+1),"w":int(R-L+1),"corner_r":res})
    print(out[-1])
json.dump(out,open("C:/t/fm_jev/bub_corner.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
