# 사용: strip.py mp4 t0 t1 step y0 y1 out.jpg [scale]
import sys, cv2, numpy as np
mp4,t0,t1,st,y0,y1,out=sys.argv[1:8]; sc=float(sys.argv[8]) if len(sys.argv)>8 else 0.5
t0,t1,st,y0,y1=float(t0),float(t1),float(st),int(y0),int(y1)
cap=cv2.VideoCapture(mp4); fps=cap.get(cv2.CAP_PROP_FPS)
cap.set(cv2.CAP_PROP_POS_MSEC, max(0,t0-0.5)*1000); rows=[]; want=t0
while want<=t1+1e-6:
    ok,f=cap.read()
    if not ok: break
    t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000-1/fps
    if t+0.5/fps>=want:
        c=f[y0:y1].copy(); cv2.putText(c,f"{want:.1f}",(5,30),0,1,(0,0,0),5); cv2.putText(c,f"{want:.1f}",(5,30),0,1,(0,255,255),2)
        rows.append(cv2.resize(c,None,fx=sc,fy=sc)); want=round(want+st,3)
g=np.vstack(rows); open(out,'wb').write(cv2.imencode('.jpg',g)[1].tobytes()); print(len(rows),g.shape)
