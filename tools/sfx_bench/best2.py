import json,sys,numpy as np,soundfile as sf,subprocess
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
SR=22050; HOP=220; NF=1024
edges=np.geomspace(80,11000,33)
fr=np.fft.rfftfreq(NF,1/SR); B=[(fr>=edges[i])&(fr<edges[i+1]) for i in range(32)]
def tf(x,L):
    n=int(L*SR); x=np.pad(x[:n],(0,max(0,n-len(x))))
    idx=np.arange(NF)[None,:]+HOP*np.arange((n-NF)//HOP)[:,None]
    S=np.abs(np.fft.rfft(x[idx]*np.hanning(NF),axis=1))
    M=np.stack([S[:,b].sum(1) for b in B],1)
    M=np.log10(M+1e-6); M=np.maximum(M,M.max()-4)   # 40dB 창
    v=M-M.mean(); return v/(np.linalg.norm(v)+1e-9)
def load(p):
    r=subprocess.run(["ffmpeg","-v","error","-i",p,"-t","2.5","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True)
    x=np.frombuffer(r.stdout,np.float32).astype(float)
    if len(x)<400: return None
    a=np.abs(x); i=max(0,np.argmax(a>a.max()*0.05)-60); return x[i:]
paths=[p for p in open("liblist.txt",encoding="utf-8").read().split("\n") if p]+[p for p in open("mk_list.txt",encoding="utf-8").read().split("\n") if p]
with ThreadPoolExecutor(8) as ex: xs=list(ex.map(load,paths))
lib=[(p,x,len(x)/SR) for p,x in zip(paths,xs) if x is not None]
rows=json.load(open("rows.json",encoding="utf-8")); cap=json.load(open("capchg.json"))
NV={}
def nv(v):
    if v not in NV: NV[v]=sf.read(f"sep/htdemucs/{v}/nv.wav")[0][::2]
    return NV[v]
def onset(x):
    a=np.abs(x); i=max(0,np.argmax(a>a.max()*0.05)-60); return x[i:]
L={"뽁":0.2,"둥":0.35,"띠링":0.45,"휙":0.25,"틱":0.12,"딸깍2":0.2}
tm={}
for typ,l in L.items():
    R=sorted([r for r in rows if r["typ"]==typ and any(abs(r["t"]-c)<=0.08 for c in cap[r["vid"]])],key=lambda r:-r["peak"])
    seen=set();pick=[]
    for r in R:
        if r["vid"] in seen: continue
        seen.add(r["vid"]); pick.append(r)
        if len(pick)==8: break
    tm[typ]=(l,[tf(onset(nv(r["vid"])[max(0,int((r["t"]-0.02)*SR)):int((r["t"]+l+0.05)*SR)]),l) for r in pick])
tm["오프너"]=(1.0,[tf(onset(nv(v)[:int(1.2*SR)]),1.0) for v in ["ABjQ0YCZoes","kC8fkx1Ve3Q","Iet-btoTSnU","1EJB0irk2Lw","d-mcihU5wNs","tcaIPaGWLrE","K5AaCbt2iLM","2sUHI8hEafE"]])
out={}
for typ,(l,ts) in tm.items():
    ceil=np.median([float(a.ravel()@b.ravel()) for i,a in enumerate(ts) for b in ts[i+1:]])
    sc=[]
    for p,x,d in lib:
        f=tf(x,l).ravel(); sc.append((float(np.median([t.ravel()@f for t in ts])),p,d))
    sc.sort(reverse=True); out[typ]={"ceil":ceil,"top":sc[:6]}
    print(f"\n■ {typ}  (이븐쇼핑 사례끼리 = {ceil:.2f})")
    for s,p,d in sc[:6]: print(f"   {s:.2f}  {d*1000:5.0f}ms  {p.split('/')[-1] if 'mixkit' in p else p.replace('C:/Users/TheRose/','')}")
json.dump(out,open("best2.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
