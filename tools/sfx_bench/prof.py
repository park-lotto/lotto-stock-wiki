import json,sys,numpy as np,soundfile as sf
sys.stdout.reconfigure(encoding="utf-8")
from feat import feats,SR
rows=json.load(open("rows.json",encoding="utf-8")); cap=json.load(open("capchg.json"))
NV={}
def nv(v):
    if v not in NV: NV[v]=sf.read(f"sep/htdemucs/{v}/nv.wav")[0][::2]
    return NV[v]
L={"뽁":0.2,"둥":0.35,"띠링":0.45,"휙":0.25,"틱":0.12,"딸깍2":0.2}
prof={}
for typ,l in L.items():
    R=[r for r in rows if r["typ"]==typ and any(abs(r["t"]-c)<=0.08 for c in cap[r["vid"]]) and r["peak"]>-26]
    F=[feats(nv(r["vid"])[max(0,int((r["t"]-0.02)*SR)):int((r["t"]+l)*SR)]) for r in R]
    prof[typ]={k:[float(np.percentile([f[k] for f in F],q)) for q in (10,50,90)] for k in F[0]}
F=[feats(nv(v)[:int(1.2*SR)]) for v in ["ABjQ0YCZoes","kC8fkx1Ve3Q","Iet-btoTSnU","1EJB0irk2Lw","d-mcihU5wNs","tcaIPaGWLrE","K5AaCbt2iLM","2sUHI8hEafE","LHembw8EUU0","1kfqEB2b1xM","CbpaHePEHHc","DkjcqgijF9Q"]]
prof["오프너"]={k:[float(np.percentile([f[k] for f in F],q)) for q in (10,50,90)] for k in F[0]}
for t,p in prof.items(): print(t,{k:[round(v) for v in vs] for k,vs in p.items()})
json.dump(prof,open("prof.json","w",encoding="utf-8"),ensure_ascii=False)
