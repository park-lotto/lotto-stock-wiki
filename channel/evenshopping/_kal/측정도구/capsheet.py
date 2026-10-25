# 자막 덩어리마다: 가운데 시각 원본 프레임 → 띠 크롭 + 창 썸네일 + 픽셀 측정(잉크 상자·채움 hex·색 낱말 hex)
import sys,json,subprocess,numpy as np,cv2
mp4,mj,out,mo=sys.argv[1:5]
d=json.load(open(mj,encoding='utf-8'))
def frame(t):
    r=subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.3f}","-i",mp4,"-frames:v","1","-f","rawvideo","-pix_fmt","bgr24","-"],capture_output=True)
    return np.frombuffer(r.stdout,np.uint8).reshape(1920,1080,3)
rows=[];meas=[]
for i,s in enumerate(d['segs']):
    tm=(s['t0']+s['t1'])/2; f=frame(tm)
    band=f[405:590]; g=cv2.cvtColor(band,cv2.COLOR_BGR2GRAY); hsv=cv2.cvtColor(band,cv2.COLOR_BGR2HSV)
    ink=g<90; ys,xs=np.where(ink)
    m={"i":i,"t":round(tm,2)}
    if len(ys)>50 and (g>235).mean()>0.5:
        m.update({"y":[int(ys.min())+405,int(ys.max())+405],"x":[int(xs.min()),int(xs.max())],"ink_h":int(ys.max()-ys.min()),"w":int(xs.max()-xs.min())})
        core=band[g<50]; m["fill_hex"]='#%02X%02X%02X'%tuple(int(v) for v in np.median(core,0)[::-1])
        col=(hsv[...,1]>90)&(hsv[...,2]>60)&(g<230)
        if col.sum()>80:
            cc=band[col]; m["color_hex"]='#%02X%02X%02X'%tuple(int(v) for v in np.median(cc,0)[::-1]); m["color_px"]=int(col.sum())
            cx=np.where(col)[1]; m["color_x"]=[int(cx.min()),int(cx.max())]
    meas.append(m)
    bc=np.vstack([cv2.resize(f[405:590],(540,92)),np.zeros((48,540,3),np.uint8)+255]); wc=cv2.resize(f[590:1810],(124,140))
    lab=np.zeros((140,110,3),np.uint8)+255
    cv2.putText(lab,f"{i}",(4,30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,0,255),2); cv2.putText(lab,f"{s['t0']:.2f}",(4,62),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,0,0),1);cv2.putText(lab,f"{s['t1']:.2f}",(4,85),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,0,0),1)
    rows.append(np.hstack([lab,bc,wc]))
half=(len(rows)+1)//2
L=rows[:half];R=rows[half:]+[np.zeros_like(rows[0])+255]*(half-len(rows[half:]))
img=np.hstack([np.vstack(L),np.zeros((140*half,8,3),np.uint8),np.vstack(R)])
cv2.imencode('.jpg',img)[1].tofile(out)
json.dump(meas,open(mo,'w',encoding='utf-8'),ensure_ascii=False)
print(len(rows))
