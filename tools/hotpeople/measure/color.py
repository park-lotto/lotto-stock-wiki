import subprocess, json, numpy as np
from collections import Counter
cj=json.load(open("cuts.json"))
def frame(f,t):
    raw=subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.2f}","-i",f,"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
    return np.frombuffer(raw,np.uint8).reshape(1920,1080,3)
def mid(f,i):
    o=cj[f]; ts=[0]+o["sub_times"]; e=o["sub_times"]+[o["dur"]]; return (ts[i-1]+e[i-1])/2
def top(px,n=4):
    q=(px//8*8).reshape(-1,3); c=Counter(map(tuple,q)); return [(tuple(int(x) for x in k),v) for k,v in c.most_common(n)]
# 배경: 아래쪽 흰 여백 (y 1600~1900)
for f in ["dvJg0By8Luw.mp4","eehzg4pzwC4.mp4","3EkwnSzxMGg.mp4"]:
    a=frame(f,30); print(f[:11],"배경",top(a[1600:1900,:,:],2))
# 형광펜: dvJ 자막1, kbx 자막1
for f,i in [("dvJg0By8Luw.mp4",1),("kbxDhWBibcc.mp4",1),("3EkwnSzxMGg.mp4",12)]:
    a=frame(f,mid(f,i)); print(f[:11],f"자막{i} 띠",top(a[1280:1460,:,:],4))
# 빨강 강조: Cmn 자막9 ('광고를 떡칠'), 헤드라인 빨강(kbx 0.5s)
a=frame("CmnmcIvwTPo.mp4",mid("CmnmcIvwTPo.mp4",9)); r=a[1280:1460].reshape(-1,3); red=r[(r[:,0]>150)&(r[:,1]<90)&(r[:,2]<90)]; print("자막 빨강 중앙값",np.median(red,axis=0).astype(int),len(red))
a=frame("kbxDhWBibcc.mp4",0.5); r=a[200:470].reshape(-1,3); red=r[(r[:,0]>150)&(r[:,1]<90)&(r[:,2]<90)]; print("헤드라인 빨강 중앙값",np.median(red,axis=0).astype(int),len(red))
a=frame("dvJg0By8Luw.mp4",0.5); r=a[200:470].reshape(-1,3); yl=r[(r[:,0]>200)&(r[:,1]>180)&(r[:,2]<90)]; print("헤드라인 노랑 중앙값",np.median(yl,axis=0).astype(int),len(yl))
