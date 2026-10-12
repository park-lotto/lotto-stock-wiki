import numpy as np
SR=22050
def feats(x):
    """타격(ms), 유효길이(-20dB까지 ms), 무게중심 주파수(Hz), 타격 횟수"""
    x=np.asarray(x,float)
    if len(x)<int(0.03*SR): x=np.pad(x,(0,int(0.03*SR)-len(x)))
    fr=int(0.005*SR); e=np.sqrt(np.convolve(x**2,np.ones(fr)/fr,"same"))+1e-9; db=20*np.log10(e/e.max())
    on=int(np.argmax(db>-30)); pk=on+int(np.argmax(db[on:on+int(0.3*SR)]))
    att=(pk-on)/SR*1000
    end=pk+int(np.argmax(db[pk:]<-20)) if (db[pk:]<-20).any() else len(x)
    L=(end-on)/SR*1000
    seg=x[on:max(end,on+int(0.02*SR))]; S=np.abs(np.fft.rfft(seg*np.hanning(len(seg)))); f=np.fft.rfftfreq(len(seg),1/SR)
    cen=float((S*f).sum()/(S.sum()+1e-9))
    # 타격 횟수: 유효구간 안 에너지 급증(직전 15ms 대비 +9dB, 30ms 간격)
    d=db[on:end]; hits=1; last=0
    for i in range(int(0.02*SR),len(d)):
        if d[i]-d[max(0,i-int(0.015*SR))]>9 and d[i]>-15 and i-last>int(0.03*SR): hits+=1; last=i
    return dict(att=att,L=L,cen=cen,hits=hits)
