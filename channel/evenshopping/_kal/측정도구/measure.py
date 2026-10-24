# evenshopping 픽셀 측정: 자막 띠 바뀜(60fps)·컷·전환·움직임
import sys, json, subprocess, numpy as np, cv2
mp4, out = sys.argv[1], sys.argv[2]
W, H = 540, 960   # 절반 크기로 디코드
p = subprocess.Popen(["ffmpeg","-v","error","-i",mp4,"-vf",f"scale={W}:{H}","-f","rawvideo","-pix_fmt","bgr24","-"],stdout=subprocess.PIPE)
fps = 60.0
r = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=r_frame_rate","-of","csv=p=0",mp4],capture_output=True,text=True).stdout.strip()
a,b = r.split("/"); fps = float(a)/float(b)
BY0,BY1 = 205,292      # 자막 흰 띠(전체 410~584)
WY0,WY1 = 300,900      # 영상 창(전체 600~1800)
ink, colored, prevmask = [], [], None
cdiff, wstats = [], []
prevw = None; prevh = None
small = []
i = 0
while True:
    buf = p.stdout.read(W*H*3)
    if len(buf) < W*H*3: break
    f = np.frombuffer(buf,np.uint8).reshape(H,W,3)
    band = f[BY0:BY1]
    g = cv2.cvtColor(band,cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(band,cv2.COLOR_BGR2HSV)
    bg_white = float((g>235).mean())
    m = (g<110)
    col = (hsv[...,1]>90)&(hsv[...,2]>90)
    ink.append((int(m.sum()), bg_white))
    colored.append(int(col.sum()))
    if prevmask is not None:
        cdiff.append(float((m ^ prevmask).sum()))
    else: cdiff.append(0.0)
    prevmask = m
    win = f[WY0:WY1]
    sm = cv2.resize(win,(90,100),interpolation=cv2.INTER_AREA)
    gw = cv2.cvtColor(sm,cv2.COLOR_BGR2GRAY)
    hs = cv2.calcHist([cv2.cvtColor(sm,cv2.COLOR_BGR2HSV)],[0,1],None,[16,8],[0,180,0,256]); cv2.normalize(hs,hs)
    lap = float(cv2.Laplacian(cv2.cvtColor(win,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var())
    d = float(np.abs(gw.astype(int)-prevw.astype(int)).mean()) if prevw is not None else 0.0
    hd = float(cv2.compareHist(prevh,hs,cv2.HISTCMP_BHATTACHARYYA)) if prevh is not None else 0.0
    wstats.append((d,hd,float(gw.mean()),lap))
    prevw, prevh = gw, hs
    if i % 3 == 0: small.append((i, cv2.cvtColor(cv2.resize(win,(180,200)),cv2.COLOR_BGR2GRAY)))
    i += 1
N = i
t = lambda k: round(k/fps,3)
# 자막 덩어리: 마스크 차이가 크면 바뀜
inkn = np.array([x[0] for x in ink]); cd = np.array(cdiff)
chg = [k for k in range(1,N) if cd[k] > max(300, 0.25*max(inkn[k],inkn[k-1],1))]
# 연속 바뀜은 묶는다(등장 애니메이션)
groups=[]
for k in chg:
    if groups and k-groups[-1][-1] <= 3: groups[-1].append(k)
    else: groups.append([k])
segs=[]; start=0
bounds=[0]+[g[0] for g in groups]+[N]
for s,e in zip(bounds,bounds[1:]):
    if e-s < 2: continue
    mid=(s+e)//2
    segs.append({"t0":t(s),"t1":t(e),"f0":s,"f1":e,"ink_mid":int(inkn[mid]),"white":round(ink[mid][1],2),"colored_mid":int(colored[mid]),
                 "ink_first5":[int(x) for x in inkn[s:s+6]], "chg_frames": next((len(g) for g in groups if g[0]==s),0)})
# 컷
ds = np.array([w[0] for w in wstats]); hd = np.array([w[1] for w in wstats]); lum = np.array([w[2] for w in wstats]); lap=np.array([w[3] for w in wstats])
cuts=[]
for k in range(1,N):
    nbr = np.median(np.concatenate([ds[max(1,k-10):k], ds[k+1:k+11]])) if N>22 else 5
    if ((hd[k] > 0.35 and ds[k] > 12) or (ds[k] > 18 and ds[k] > 3.0*nbr and hd[k] > 0.1)) and ds[k] >= ds[max(0,k-3):k+4].max() and (not cuts or k-cuts[-1]["f"] > 6):
        lo=max(0,k-6); hi=min(N,k+6)
        nb = np.median(lap[max(0,k-20):max(1,k-8)].tolist()+lap[min(N-1,k+8):min(N,k+20)].tolist()) if N>40 else lap.mean()
        tr="cut"
        if lum[lo:hi].max() > 215 and lum[lo:hi].max() > lum[max(0,k-20)]+40: tr="flash"
        elif lum[lo:hi].min() < 20: tr="black"
        elif lap[lo:hi].min() < 0.2*nb: tr="blur_check"
        cuts.append({"t":t(k),"f":k,"hd":round(hd[k],2),"d":round(ds[k],1),"tr":tr,"lap_min_ratio":round(float(lap[lo:hi].min()/max(nb,1e-6)),2),"lum_rng":[round(float(lum[lo:hi].min())),round(float(lum[lo:hi].max()))]})
# 움직임: 샷마다 3프레임 간격 전역 닮음변환
shots=[]
cb=[0]+[c["f"] for c in cuts]+[N]
idx={fi:j for j,(fi,_) in enumerate(small)}
for s,e in zip(cb,cb[1:]):
    fr=[(fi,im) for fi,im in small if s+2<=fi<e-2]
    sc=[];tx=[];ty=[]
    for (f1,a1),(f2,a2) in zip(fr,fr[1:]):
        pts=cv2.goodFeaturesToTrack(a1,150,0.01,6)
        if pts is None or len(pts)<10: continue
        p2,st,_=cv2.calcOpticalFlowPyrLK(a1,a2,pts,None)
        ok=st.ravel()==1
        if ok.sum()<10: continue
        M,_=cv2.estimateAffinePartial2D(pts[ok],p2[ok])
        if M is None: continue
        sc.append(float(np.sqrt(M[0,0]**2+M[0,1]**2))); tx.append(float(M[0,2])); ty.append(float(M[1,2]))
    if sc:
        S=float(np.prod(sc)); TX=float(np.sum(tx)); TY=float(np.sum(ty)); jit=float(np.mean(np.abs(tx))+np.mean(np.abs(ty)))
    else: S,TX,TY,jit=1.0,0,0,0
    dur=(e-s)/fps
    if S>1.04: mo="zoom_in"
    elif S<0.96: mo="zoom_out"
    elif abs(TX)+abs(TY) > 40: mo="pan"
    elif jit < 0.25: mo="still"
    else: mo="cam"
    shots.append({"t0":t(s),"t1":t(e),"scale":round(S,3),"tx":round(TX,1),"ty":round(TY,1),"jit":round(jit,2),"motion":mo})
json.dump({"fps":fps,"N":N,"dur":t(N),"segs":segs,"cuts":cuts,"shots":shots,"raw":[[round(w[0],1),round(w[1],3)] for w in wstats]},open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=0)
print(out, "segs",len(segs),"cuts",len(cuts))
