# 옮김: tools/calcopy/engine/readline_tools/tone.py (관제 263 지시서 13, 10-25 — 새 작업은 그쪽을 쓴다. 이 파일은 기록용으로 남김)
# 말 위에 얹힌 지속 순음(띵·딩동) 찾기: 2.5~6kHz 각 칸(±1칸)이 주파수 주변보다 >=14dB 로 0.12초+ 유지 → 0.35초 안은 한 사건
import sys,subprocess,numpy as np,json
from scipy.signal import stft
from scipy.ndimage import median_filter, maximum_filter1d
res={}
for vid in sys.argv[1:]:
    r=subprocess.run(["ffmpeg","-v","error","-i",f"C:/숏템_칼카피/evenshopping/src/{vid}.mp4","-ac","1","-ar","22050","-f","s16le","-"],capture_output=True)
    x=np.frombuffer(r.stdout,np.int16).astype(np.float32)/32768
    f,t,Z=stft(x,22050,nperseg=2048,noverlap=2048-256); L=10*np.log10(np.abs(Z)**2+1e-12)
    m=(f>=2500)&(f<=6000); S=L[m]; ff=f[m]
    P=S-median_filter(S,size=(15,1),mode='nearest'); P=maximum_filter1d(P,3,axis=0)
    ok=P>=14; hits=[]
    dt=t[1]-t[0]; need=int(0.12/dt)
    for b in range(ok.shape[0]):
        row=ok[b]; i=0
        while i<len(row):
            if row[i]:
                j=i
                while j+1<len(row) and row[j+1]: j+=1
                if j-i+1>=need: hits.append((float(t[i]),float(t[j]),int(ff[b]),float(np.median(P[b,i:j+1]))))
                i=j+1
            else: i+=1
    hits.sort(); ev=[]
    for a,b,hz,p in hits:
        if ev and a-ev[-1]["t1"]<0.35:
            e=ev[-1]; e["t1"]=max(e["t1"],b); e["hz"].add(round(hz/50)*50); e["prom"]=max(e["prom"],p)
        else: ev.append({"t":a,"t1":b,"hz":{round(hz/50)*50},"prom":p})
    out=[{"t":round(e["t"],2),"dur":round(e["t1"]-e["t"],2),"hz":sorted(e["hz"])[:4],"prom_db":round(e["prom"],1)} for e in ev]
    res[vid]=out; print(vid,len(out),[(o["t"],o["dur"],o["hz"][:2]) for o in out])
json.dump(res,open("C:/숏템_칼카피/evenshopping/work/tone_detect.json","w"),indent=0)
