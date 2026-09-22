import json,sys,glob,os,numpy as np,soundfile as sf,collections
sys.stdout.reconfigure(encoding="utf-8")
exec(open("pool.py",encoding="utf-8").read().split("paths=[p for p")[0])   # tf/onset/SR 재사용
prof=json.load(open("prof.json",encoding="utf-8")); rows=json.load(open("rows.json",encoding="utf-8")); cap=json.load(open("capchg.json"))
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
    s=set();pk=[]
    for r in R:
        if r["vid"] in s: continue
        s.add(r["vid"]); pk.append(r)
        if len(pk)==8: break
    tm[typ]=[tf(onset(nv(r["vid"])[max(0,int((r["t"]-0.02)*SR)):int((r["t"]+l+0.05)*SR)]),l) for r in pk]
MAP={"오프너":"오프너","뽁":"뽁","둥":"둥","띠링":"띠링","휙":"휙","틱":"틱","딸깍딸깍":"딸깍2"}
per=collections.defaultdict(list); res=collections.defaultdict(list); lv=collections.defaultdict(list); n=0
for f in glob.glob("C:/Users/TheRose/Desktop/이븐쇼핑_효과음_벤치마크/3_효과음팩/팩*/[0-6]_*.wav"):
    typ=MAP[os.path.basename(f).split("_")[1]]
    x,sr=sf.read(f); fr=int(0.02*sr); lv[typ].append(20*np.log10(np.sqrt(np.convolve(x**2,np.ones(fr)/fr,"valid")).max()))
    y=onset(x[::2]); s=float(np.median([t@tf(y,LEN[typ]) for t in tm[typ]])); res[typ].append(s); n+=1; per[os.path.basename(f).split("_")[2][:-4]].append(s)
print("검사 파일",n)
for t in LEN: print(f"{t:4s} 파일{len(res[t]):3d}  이븐쇼핑유사 최저 {min(res[t]):.2f} 중앙 {np.median(res[t]):.2f}  세기 {np.median(lv[t]):.1f}dB")
print({k:round(float(np.mean(v)),2) for k,v in sorted(per.items())})
