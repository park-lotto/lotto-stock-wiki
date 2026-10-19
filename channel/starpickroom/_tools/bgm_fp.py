"""BGM 템포·밝기 + 우리 BGM 라이브러리(shopping_shorts/assets/bgm_lib) 크로마 지문 대조. 로컬 numpy/scipy.
python bgm_fp.py <wav폴더> <출력json> [--calib]
크로마: 80~2000Hz STFT(4096, hop 0.5s 평균) 12음 -> 벤치 전체 평균 크로마 vs 라이브러리 곡 슬라이딩 평균 크로마 코사인(키·화성 일치). 나레 목소리가 섞이므로 보정(--calib)으로 회수율을 먼저 잰다."""
import sys, os, glob, json, subprocess
import numpy as np
from scipy.signal import stft
sys.path.insert(0, os.path.dirname(__file__))
import sfx_fp as F
SR=F.SR
def chroma_seq(x, hop_s=0.5):
    nf=4096; h=int(hop_s*SR)
    _,_,Z=stft(x,SR,nperseg=nf,noverlap=nf-h,boundary=None,padded=False)
    fr=np.fft.rfftfreq(nf,1/SR); m=(fr>=80)&(fr<=2000); P=np.abs(Z[m])**2; f=fr[m]
    pc=(np.round(12*np.log2(f/440.0))%12).astype(int); C=np.zeros((12,P.shape[1]))
    for k in range(12): C[k]=P[pc==k].sum(0)
    C=np.log1p(C/ (C.mean()+1e-12)); return C
def tempo(x):
    # 저역(40~250Hz)+전대역 스펙트럴 플럭스 자기상관 -> 60~180 BPM
    _,_,Z=stft(x,SR,nperseg=1024,noverlap=1024-256,boundary=None,padded=False)
    fr=np.fft.rfftfreq(1024,1/SR); res={}
    for name,(a,b) in {'low':(40,250),'all':(60,8000)}.items():
        m=(fr>=a)&(fr<=b); E=np.log1p(np.abs(Z[m]))
        fl=np.maximum(np.diff(E,axis=1),0).sum(0); fl=fl-fl.mean()
        ac=np.correlate(fl,fl,'full')[len(fl)-1:]; ac/=ac[0]+1e-9; fps=SR/256
        lags=np.arange(int(fps*60/180),int(fps*60/60)); j=lags[np.argmax(ac[lags])]
        res[name]=round(60*fps/j,1); res[name+'_ac']=round(float(ac[j]),2)
    return res
def bright(x):
    _,_,Z=stft(x,SR,nperseg=2048,noverlap=1024,boundary=None,padded=False); P=(np.abs(Z)**2).mean(1); fr=np.fft.rfftfreq(2048,1/SR)
    return round(float((fr*P).sum()/P.sum()),0)
def libtracks():
    out={}
    for p in sorted(glob.glob('shopping_shorts/assets/bgm_lib/*.mp3')): out[os.path.basename(p)[:-4]]=F.load(p)
    return out
def best_match(C,libC):
    n=C.shape[1]; v=C.mean(1); v=v-v.mean(); res=[]
    for k,L in libC.items():
        if L.shape[1]<n: seg=[L.mean(1)]
        else: seg=[L[:,i:i+n].mean(1) for i in range(0,L.shape[1]-n+1,2)]
        s=max(float(np.dot(v,u-u.mean())/(np.linalg.norm(v)*np.linalg.norm(u-u.mean())+1e-9)) for u in seg)
        res.append((k,round(s,3)))
    res.sort(key=lambda a:-a[1]); return res
if __name__=='__main__':
    lib=libtracks(); libC={k:chroma_seq(v) for k,v in lib.items()}
    if '--calib' in sys.argv:
        sp=F.load('shopping_shorts/assets/voice_samples/tc-changsu-stable.mp3'); rng=np.random.default_rng(0); ok1=ok3=n=0
        for k,v in lib.items():
            L=min(len(v),int(17*SR)); s0=int(rng.integers(0,max(1,len(v)-L))); b=v[s0:s0+L]
            sp2=np.tile(sp,int(np.ceil(L/len(sp))))[:L]
            y=b/np.sqrt((b**2).mean()+1e-9)+sp2/np.sqrt((sp2**2).mean()+1e-9)*10**(6/20)   # 말이 BGM보다 6dB 큼
            r=best_match(chroma_seq(y),libC); n+=1; ok1+=r[0][0]==k; ok3+=k in [a for a,_ in r[:3]]
        print('보정(말 +6dB 위에 BGM): top1',ok1,'/',n,'top3',ok3,'/',n); sys.exit()
    res={}
    for w in sorted(glob.glob(os.path.join(sys.argv[1],'*.wav'))):
        x=F.load(w); n=os.path.basename(w)[:-4]; r=best_match(chroma_seq(x),libC)
        res[n]={'tempo':tempo(x),'centroid_hz':bright(x),'match':r[:3],'dur':round(len(x)/SR,1)}; print(n,res[n],flush=True)
    json.dump(res,open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False,indent=1)
