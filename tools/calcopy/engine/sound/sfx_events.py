"""라이브러리 없이 효과음 후보 사건을 신호 모양으로 찾는다 (로컬).
 broad : 5~10.5kHz 에너지가 ±0.75초 중앙값보다 >= BR_DB 솟고(0.05~0.7초), 그 사이 유성 f0 없음 -> '휙·틱·뽁·딸깍' 류 (치찰음 /s/ 와 구분 약함 — 길이로 보조)
 tonal : 1~6kHz 에서 한 주파수 봉우리가 0.2초 이상 유지, 주변 대비 >= TN_DB, 유성 f0 없음 -> '띵·띠링' 류
 python sfx_events.py <wav> -> json 줄 / 함수 detect(x) -> list"""
import sys, os, json
import numpy as np
from scipy.signal import stft, find_peaks
from scipy.ndimage import median_filter
sys.path.insert(0, os.path.dirname(__file__))
import sfx_fp as F, voice_fp as V
SR=F.SR; NF=1024; HOP=256; FPS=SR/HOP
BR_DB=18; TN_DB=22
def detect(x):
    f,t,Z=stft(x,SR,nperseg=NF,noverlap=NF-HOP,boundary=None,padded=False); P=np.abs(Z)**2+1e-12
    L=10*np.log10(P)
    # 유성 마스크 (f0 트랙 10ms -> 프레임 격자)
    f0,_=V.f0_track(x.astype(np.float32)); vt=np.arange(len(f0))*0.01+0.02
    voiced=np.interp(t,vt,(f0>0).astype(float))>0.5
    out=[]
    # broad
    m=(f>=5000)&(f<=10500); hf=10*np.log10(P[m].sum(0)); med=median_filter(hf,size=int(1.5*FPS)|1,mode='nearest'); ex=hf-med
    pk,_=find_peaks(ex,height=BR_DB,distance=int(0.15*FPS))
    for p in pk:
        a=p
        while a>0 and ex[a-1]>BR_DB*0.5: a-=1
        b=p
        while b<len(ex)-1 and ex[b+1]>BR_DB*0.5: b+=1
        dur=(b-a+1)/FPS
        if not (0.05<=dur<=0.7): continue
        vf=voiced[max(0,a-3):b+4].mean()
        w=int(0.12*FPS); iso=1.0-float(np.concatenate([voiced[max(0,a-w):a],voiced[b+1:b+1+w]]).mean()) if (a>0 or b<len(voiced)-1) else 1.0
        cen=float((f[m]*P[m][:,p]).sum()/P[m][:,p].sum())
        out.append({'t':round(float(t[a]),2),'kind':'broad','dur':round(dur,2),'db':round(float(ex[p]),1),'voiced':round(float(vf),2),'isolated':round(iso,2),'cen_hz':round(cen)})
    # tonal
    m2=(f>=1000)&(f<=6000); S=L[m2]; ff=f[m2]; k=S.argmax(0); prom=S.max(0)-np.median(S,axis=0)
    ok=(prom>=TN_DB)&(~voiced)
    i=0
    while i<len(ok):
        if ok[i]:
            j=i
            while j+1<len(ok) and ok[j+1] and abs(k[j+1]-k[j])<=3: j+=1
            dur=(j-i+1)/FPS
            if dur>=0.2: out.append({'t':round(float(t[i]),2),'kind':'tonal','dur':round(dur,2),'db':round(float(prom[i:j+1].max()),1),'cen_hz':round(float(ff[int(np.median(k[i:j+1]))]))}); 
            i=j+1
        else: i+=1
    out.sort(key=lambda e:e['t']); return out
if __name__=='__main__':
    x=F.load(sys.argv[1]); print(json.dumps(detect(x),ensure_ascii=False))
