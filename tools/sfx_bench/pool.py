import json,sys,numpy as np,soundfile as sf,subprocess,hashlib
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
from feat import feats,SR
HOP=220; NF=1024
edges=np.geomspace(80,11000,33); fr=np.fft.rfftfreq(NF,1/SR); B=[(fr>=edges[i])&(fr<edges[i+1]) for i in range(32)]
def tf(x,L):
    n=int(L*SR); x=np.pad(x[:n],(0,max(0,n-len(x))))
    idx=np.arange(NF)[None,:]+HOP*np.arange((n-NF)//HOP)[:,None]
    S=np.abs(np.fft.rfft(x[idx]*np.hanning(NF),axis=1)); M=np.stack([S[:,b].sum(1) for b in B],1)
    M=np.log10(M+1e-6); M=np.maximum(M,M.max()-4); v=(M-M.mean()).ravel(); return v/(np.linalg.norm(v)+1e-9)
def onset(x):
    a=np.abs(x); i=max(0,np.argmax(a>a.max()*0.05)-60); return x[i:]
def load(p):
    r=subprocess.run(["ffmpeg","-v","error","-i",p,"-t","3","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True)
    x=np.frombuffer(r.stdout,np.float32).astype(float)
    return onset(x) if len(x)>400 and np.abs(x).max()>1e-4 else None
paths=[p for p in open("pool.txt",encoding="utf-8").read().split("\n") if p]
with ThreadPoolExecutor(8) as ex: xs=list(ex.map(load,paths))
# 중복 제거: 앞 0.5초 파형 해시(반올림)
seen={}; lib=[]
for p,x in zip(paths,xs):
    if x is None: continue
    h=hashlib.md5(np.round(x[:int(0.5*SR)]*200).astype(np.int16).tobytes()).hexdigest()
    if h in seen: continue
    seen[h]=p; lib.append((p,x))
print("후보 파일(중복 뺌)",len(lib))
prof=json.load(open("prof.json",encoding="utf-8"))
rows=json.load(open("rows.json",encoding="utf-8")); cap=json.load(open("capchg.json"))
NV={}
def nv(v):
    if v not in NV: NV[v]=sf.read(f"sep/htdemucs/{v}/nv.wav")[0][::2]
    return NV[v]
LEN={"뽁":0.2,"둥":0.35,"띠링":0.45,"휙":0.25,"틱":0.12,"딸깍2":0.2,"오프너":1.0}
tm={}
for typ,l in LEN.items():
    if typ=="오프너":
        tm[typ]=[tf(onset(nv(v)[:int(1.2*SR)]),l) for v in ["ABjQ0YCZoes","kC8fkx1Ve3Q","Iet-btoTSnU","1EJB0irk2Lw","d-mcihU5wNs","tcaIPaGWLrE","K5AaCbt2iLM","2sUHI8hEafE"]]; continue
    R=sorted([r for r in rows if r["typ"]==typ and any(abs(r["t"]-c)<=0.08 for c in cap[r["vid"]])],key=lambda r:-r["peak"])
    seen2=set();pick=[]
    for r in R:
        if r["vid"] in seen2: continue
        seen2.add(r["vid"]); pick.append(r)
        if len(pick)==8: break
    tm[typ]=[tf(onset(nv(r["vid"])[max(0,int((r["t"]-0.02)*SR)):int((r["t"]+l+0.05)*SR)]),l) for r in pick]
def gate(typ,f):
    p=prof[typ]; why=[]
    if not (p["cen"][0]/1.5<=f["cen"]<=p["cen"][2]*1.5): why.append("음높이")
    if not (p["L"][0]*0.5<=f["L"]<=p["L"][2]*1.8): why.append("길이")
    if f["att"]>max(p["att"][2]*1.5,40): why.append("타격느림")
    if typ=="오프너":
        if f["hits"]<2: why.append("타격수")
    elif not (p["hits"][0]<=f["hits"]<=p["hits"][2]+1): why.append("타격수")
    return why
out={}
for typ,l in LEN.items():
    c=[]
    for p,x in lib:
        seg=x[:int(l*SR)]; f=feats(seg)
        if gate(typ,f): continue
        s=float(np.median([t@tf(seg,l) for t in tm[typ]]))
        c.append(dict(p=p,score=s,**f))
    c.sort(key=lambda d:-d["score"])
    # 서로 너무 닮은 후보(지문 0.97+)는 하나만
    keep=[];fps=[]
    for d in c:
        x=dict(lib)[d["p"]]; v=tf(x[:int(l*SR)],l)
        if any(v@u>0.97 for u in fps): continue
        keep.append(d); fps.append(v)
        if len(keep)==12: break
    ceil=float(np.median([a@b for i,a in enumerate(tm[typ]) for b in tm[typ][i+1:]]))
    out[typ]={"ceil":ceil,"cands":keep}
    print(f"\n■ {typ} 기준선 {ceil:.2f} · 거름망 통과 {len(c)}개")
    for d in keep[:8]: print(f"   {d['score']:.2f} 길이{d['L']:4.0f}ms 중심{d['cen']:5.0f}Hz 타격{d['hits']}  {d['p'].split('/')[-1]}")
json.dump(out,open("pool.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
