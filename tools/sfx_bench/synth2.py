import numpy as np,soundfile as sf,os
SR=44100; rng=np.random.default_rng(11)
os.makedirs("synth2",exist_ok=True)
def env(t,att,tau): return np.minimum(t/att,1)*np.exp(-t/tau)
def click(n,amp): return rng.standard_normal(n)*np.linspace(1,0,n)*amp
def dung(f0,hi,tau,bright):
    t=np.arange(int(0.32*SR))/SR
    f1=np.where(t<0.07,hi-hi*0.8*t,0); h=np.sin(2*np.pi*np.cumsum(f1)/SR)*(t<0.075)*0.6*np.exp(-t/0.05)
    tt=np.maximum(t-0.03,0); lo=sum(a*np.sin(2*np.pi*f0*k*t) for k,a in [(1,1.0),(2,0.6*bright),(3,0.4*bright),(5,0.15*bright)])*env(tt,0.004,tau)*(t>0.03)
    y=h+lo; y[:260]+=click(260,0.6); return y/np.abs(y).max()*0.89
i=0
for f0 in (230,270,310):
    for hi in (780,870,960):
        for tau,br in ((0.06,1.0),(0.08,0.7)):
            if rng.random()<0.45: continue
            i+=1; sf.write(f"synth2/둥합성_{f0}Hz_{hi}_{int(tau*1000)}ms.wav",dung(f0,hi,tau,br),SR)
print(i,"개")
