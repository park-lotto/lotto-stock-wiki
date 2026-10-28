import numpy as np,soundfile as sf,sys,os
sys.stdout.reconfigure(encoding="utf-8")
SR=44100; rng=np.random.default_rng(7)
def t(d): return np.arange(int(d*SR))/SR
def env(tt,att,tau): return np.minimum(tt/att,1)*np.exp(-tt/tau)
def click(d=0.004,amp=0.3):
    n=int(d*SR); return rng.standard_normal(n)*np.linspace(1,0,n)*amp
def pad(x,d): return np.pad(x,(0,max(0,int(d*SR)-len(x))))[:int(d*SR)]
def ttiring():
    tt=t(0.45); P=[(2280,1.0,0.12),(4292,0.8,0.09),(5815,0.7,0.08),(9695,0.45,0.05),(9765,0.35,0.05),(12842,0.3,0.035),(12925,0.25,0.035)]
    y=sum(a*np.sin(2*np.pi*f*tt)*env(tt,0.002,tau) for f,a,tau in P)
    y[:len(click())]+=click(amp=0.4); return y
def ppok():
    tt=t(0.12); f=290*(750/290)**np.minimum(tt/0.08,1); ph=2*np.pi*np.cumsum(f)/SR
    y=np.sin(ph)*env(tt,0.003,0.035)+0.3*np.sin(2*ph)*env(tt,0.003,0.02); y[:len(click())]+=click(amp=0.5); return y
def dung():
    tt=t(0.32); f1=np.where(tt<0.07,870-700*tt,0); hi=np.sin(2*np.pi*np.cumsum(f1)/SR)*(tt<0.075)*0.6*np.exp(-tt/0.05)
    lo=sum(a*np.sin(2*np.pi*f*tt) for f,a in [(270,1.0),(540,0.6),(810,0.4),(1400,0.15)])*env(np.maximum(tt-0.03,0),0.004,0.07)*(tt>0.03)
    y=hi+lo; y[:len(click(0.006))]+=click(0.006,0.6); return y
def opener():
    y=np.zeros(int(1.0*SR))
    for s,a in [(0.0,1.0),(0.12,0.9)]:
        n=int(0.018*SR); i=int(s*SR); y[i:i+n]+=rng.standard_normal(n)*np.exp(-np.arange(n)/SR/0.004)*a
    tt=t(0.9); i=int(0.12*SR); th=np.sin(2*np.pi*(90-30*tt)*tt)*env(tt,0.003,0.12)*0.9; y[i:i+len(th)]+=th[:len(y)-i]
    tail=rng.standard_normal(len(y))*0.02*np.exp(-np.arange(len(y))/SR/0.35); from scipy.signal import butter,lfilter
    b,a=butter(2,[2000/(SR/2),9000/(SR/2)],"band"); y+=lfilter(b,a,tail)*3; return y
os.makedirs("synth",exist_ok=True)
for n,fn in [("띠링",ttiring),("뽁",ppok),("둥",dung),("오프너",opener)]:
    y=fn(); y=y/np.abs(y).max()*0.7; sf.write(f"synth/{n}.wav",y,SR)
print("ok")
