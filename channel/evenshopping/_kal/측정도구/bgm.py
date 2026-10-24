import sys,subprocess,numpy as np,json
from scipy.signal import stft
res={}
for vid in sys.argv[1:]:
    mp4=f"C:/숏템_칼카피/evenshopping/src/{vid}.mp4"
    r=subprocess.run(["ffmpeg","-v","error","-i",mp4,"-ac","1","-ar","16000","-f","s16le","-"],capture_output=True)
    x=np.frombuffer(r.stdout,np.int16).astype(np.float32)/32768
    hop=160; n=len(x)//hop; e=np.array([np.sqrt(np.mean(x[i*hop:(i+1)*hop]**2)+1e-12) for i in range(n)]); db=20*np.log10(e+1e-9)
    # 쉼: 30ms 이상 연속으로 말 최대보다 25dB 낮은 구간
    thr=np.percentile(db,95)-25
    q=db<thr
    runs=[];i=0
    while i<n:
        if q[i]:
            j=i
            while j<n and q[j]: j+=1
            if j-i>=4: runs.append((i,j))
            i=j
        else: i+=1
    pause=np.concatenate([db[a:b] for a,b in runs]) if runs else np.array([])
    # 쉼 안 스펙트럼: 조성(봉우리) 정도
    ton=[]
    for a,b in runs:
        seg=x[a*hop:b*hop]
        if len(seg)<1024: continue
        f,t,Z=stft(seg,16000,nperseg=1024); P=(np.abs(Z)**2).mean(1); m=(f>80)&(f<4000)
        Pm=P[m]; ton.append(float(10*np.log10(Pm.max()/np.median(Pm))))
    lufs=subprocess.run(["ffmpeg","-hide_banner","-i",mp4,"-af","ebur128","-f","null","-"],capture_output=True,text=True,encoding='utf-8',errors='replace').stderr
    import re
    I=re.findall(r"I:\s+(-?[\d.]+) LUFS",lufs)
    res[vid]={"lufs":float(I[-1]) if I else None,"speech_p95_db":round(float(np.percentile(db,95)),1),"n_pause":len(runs),"pause_sec":round(sum(b-a for a,b in runs)*0.01,2),
              "pause_med_db":round(float(np.median(pause)),1) if len(pause) else None,"pause_p10_db":round(float(np.percentile(pause,10)),1) if len(pause) else None,
              "pause_tonal_med_db":round(float(np.median(ton)),1) if ton else None,"floor_rel":round(float(np.median(pause))-float(np.percentile(db,95)),1) if len(pause) else None}
    print(vid,res[vid])
json.dump(res,open("C:/숏템_칼카피/evenshopping/work/bgm_check.json","w"),indent=1)
