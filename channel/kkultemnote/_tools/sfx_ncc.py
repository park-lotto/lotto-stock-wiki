"""효과음 원본 복사 여부 — 파형 정규화 상호상관(NCC, 1.5~10kHz 대역, FFT). 같은 파일을 재인코딩·BGM과 섞어 썼으면 피크가 솟는다.
(스펙트럼 코사인 지문은 보정 시험에서 12개 중 2개만 회수 -> 폐기. 이 방법은 --calib 로 회수율을 먼저 잰다.)
python sfx_ncc.py <wav폴더> <출력json> [--calib <wav>]"""
import sys, os, glob, json
import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve
sys.path.insert(0, os.path.dirname(__file__))
import sfx_fp as F
SR=F.SR
SOS=butter(4,[1500,10000],btype='band',fs=SR,output='sos')
def bp(x): return sosfiltfilt(SOS,x.astype(np.float64))
def templates():
    lib=F.library(); T={}
    for k,v in lib.items():
        x=F.load(v['path'])
        if len(x)<int(0.05*SR): continue
        x=bp(x); e=np.abs(x); idx=np.where(e>e.max()*0.03)[0]
        if len(idx)==0: continue
        x=x[idx[0]:idx[0]+int(1.2*SR)]
        x=x/ (np.linalg.norm(x)+1e-12); T[k]=x
    return T,lib
def scan(x,T,thr=0.35):
    from scipy.fft import rfft, irfft, next_fast_len
    y=bp(x); N=next_fast_len(len(y)+1300*SR//1000+int(1.2*SR)); Y=rfft(y,N)
    c2=np.concatenate([[0],np.cumsum(y**2)]); hits=[]
    for k,t in T.items():
        n=len(t)
        if len(y)<n: continue
        num=irfft(Y*np.conj(rfft(t,N)),N)[:len(y)-n+1]
        en=np.sqrt(np.maximum(c2[n:]-c2[:-n],1e-12)); c=num/en
        order=np.argsort(-c)[:60]; taken=[]
        for i in order:
            if c[i]<thr: break
            if all(abs(i-a)>0.3*SR for a in taken): taken.append(i); hits.append({'t':round(i/SR,2),'file':k,'ncc':round(float(c[i]),3)})
    hits.sort(key=lambda h:-h['ncc']); return hits
def calib(wav,T,lib):
    x=F.load(wav); rng=np.random.default_rng(1); ks=list(T); out={}
    for gain in (0.5,0.25,0.12):
        ok=0;n=0;vals=[]
        for tr in range(8):
            k=ks[rng.integers(len(ks))]; s=F.load(lib[k]['path']); s=s/(np.abs(s).max()+1e-9)*gain*np.abs(x).max()
            t0=2+tr*1.4; i=int(t0*SR); y=x.copy(); y[i:i+len(s)]+=s[:len(y)-i]
            h=scan(y,{kk:T[kk] for kk in ks},0.2)
            top=h[0] if h else None; n+=1
            if top and top['file']==k and abs(top['t']-t0)<0.4: ok+=1
            if top: vals.append(top['ncc'])
        out[gain]={'top1_ok':ok,'n':n}
    return out
if __name__=='__main__':
    T,lib=templates(); print('템플릿',len(T),flush=True)
    if '--calib' in sys.argv:
        print(calib(sys.argv[sys.argv.index('--calib')+1],T,lib)); sys.exit()
    res={}
    for w in sorted(glob.glob(os.path.join(sys.argv[1],'*.wav'))):
        n=os.path.basename(w)[:-4]; h=scan(F.load(w),T)
        res[n]=h[:30]; print(n,[(a['t'],a['file'].split('/')[-1][-28:],a['ncc']) for a in h[:5]],flush=True)
    json.dump({'res':res,'also':{k:v['also'] for k,v in lib.items()}},open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False,indent=1)
