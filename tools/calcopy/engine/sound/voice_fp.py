"""나레 목소리 지표 + 우리 목소리 견본 유사도 (로컬 numpy/scipy, 외부 전송 없음).
특징: f0(자기상관, 40ms/10ms) 중앙·반음 표준편차·인접프레임 변화(미세 변동)·유성비, 쉼 규칙성(>=80ms 무성 구간 길이 변동계수),
     MFCC(20) 평균(유성 프레임) -> 평균 제거 없이 코사인/거리, LPC 포먼트 F1~F3 중앙.
함수: feats(x, sr=22050) -> dict"""
import numpy as np
from scipy.fft import dct
from scipy.signal import stft, lfilter
SR=22050
def frames(x, n, h):
    k=1+(len(x)-n)//h
    from numpy.lib.stride_tricks import as_strided
    return as_strided(x,(k,n),(x.strides[0]*h,x.strides[0]),writeable=False)
def f0_track(x, sr=SR):
    n=int(0.04*sr); h=int(0.01*sr)
    if len(x)<n*2: return np.zeros(0),np.zeros(0)
    F=frames(x,n,h)*np.hanning(n); lo=int(sr/400); hi=int(sr/70)
    f0=np.zeros(len(F)); rms=np.sqrt((F**2).mean(1))
    for i,f in enumerate(F):
        if rms[i]<1e-4: continue
        a=np.correlate(f,f,'full')[n-1:]
        if a[0]<=0: continue
        a=a/a[0]; seg=a[lo:hi]; j=seg.argmax()
        if seg[j]>0.55: f0[i]=sr/(lo+j)
    return f0,rms
def mfcc(x, sr=SR, nm=40, nc=20):
    nf=1024; _,_,Z=stft(x,sr,nperseg=nf,noverlap=nf-256,boundary=None,padded=False)
    P=np.abs(Z)**2; fr=np.fft.rfftfreq(nf,1/sr)
    mel=lambda v:2595*np.log10(1+v/700); inv=lambda m:700*(10**(m/2595)-1)
    pts=inv(np.linspace(mel(60),mel(8000),nm+2)); B=np.zeros((nm,len(fr)))
    for i in range(nm):
        a,b,c=pts[i],pts[i+1],pts[i+2]; B[i]=np.clip(np.minimum((fr-a)/(b-a),(c-fr)/(c-b)),0,None)
    L=np.log(B@P+1e-10); return dct(L,axis=0,norm='ortho')[1:nc+1].T   # (T,20) 프레임 hop 256
def lpc_formants(x, sr=SR, order=14):
    y=np.append(x[0],x[1:]-0.97*x[:-1])*np.hamming(len(x))
    r=np.correlate(y,y,'full')[len(y)-1:len(y)+order]
    if r[0]<=0: return None
    from scipy.linalg import solve_toeplitz
    try: a=solve_toeplitz(r[:order],r[1:order+1])
    except Exception: return None
    roots=np.roots(np.concatenate([[1],-a])); roots=roots[np.imag(roots)>0]
    fr=sorted(np.angle(roots)*sr/(2*np.pi)); bw=-np.log(np.abs(roots))*sr/np.pi
    out=[f for f,(b) in zip(np.angle(roots)*sr/(2*np.pi),bw) if 200<f<3800 and b<400]
    return sorted(out)[:3] if len(out)>=3 else None
def feats(x, sr=SR):
    x=x.astype(np.float32); x=x/(np.abs(x).max()+1e-9)
    f0,rms=f0_track(x,sr); v=f0>0
    d={'dur':round(len(x)/sr,2),'voiced_ratio':round(float(v.mean()),3) if len(f0) else 0}
    if v.sum()<15: return d
    st=12*np.log2(f0[v]/100.)
    d['f0_med']=round(float(np.median(f0[v])),1); d['f0_p10']=round(float(np.percentile(f0[v],10)),1); d['f0_p90']=round(float(np.percentile(f0[v],90)),1)
    d['st_std']=round(float(st.std()),2)
    idx=np.where(v)[0]; adj=idx[1:]==idx[:-1]+1; dst=np.abs(np.diff(st))[adj]
    d['micro_dst']=round(float(np.median(dst)),3)       # 인접 프레임 반음 변화 중앙(작을수록 매끈)
    d['micro_p90']=round(float(np.percentile(dst,90)),3)
    # 쉼: 무성 연속 구간(>=8프레임=80ms) 길이
    runs=[];c=0
    for z in v:
        if not z: c+=1
        else:
            if c>=8: runs.append(c)
            c=0
    d['pause_n']=len(runs); d['pause_cv']=round(float(np.std(runs)/np.mean(runs)),2) if len(runs)>=3 else None
    # 진폭 변동(shimmer 근사): 유성 프레임 rms 인접 변화 비율
    r=rms[v]; d['shim']=round(float(np.median(np.abs(np.diff(r))[adj]/(r[1:][adj]+1e-9))),3)
    M=mfcc(x,sr); tm=np.arange(len(M))*256/sr; vi=np.clip((tm/0.01).astype(int),0,len(v)-1); mv=v[vi]
    if mv.sum()>10: d['mfcc']=M[mv].mean(0).round(3).tolist()
    # 포먼트
    fm=[];n=int(0.03*sr)
    for i in idx[::6][:200]:
        s=i*int(0.01*sr); seg=x[s:s+n]
        if len(seg)==n:
            q=lpc_formants(seg,sr)
            if q: fm.append(q)
    if len(fm)>=8: d['formants']=np.median(np.array(fm),0).round(0).tolist()
    return d
