import json,sys,collections,numpy as np
sys.stdout.reconfigure(encoding="utf-8")
p=json.load(open("prep.json",encoding="utf-8")); ev=json.load(open("events.json")); ty=json.load(open("types.json",encoding="utf-8")); sec=json.load(open("sections.json",encoding="utf-8"))
MAIN=["뽁","둥","띠링","휙","틱","딸깍2","촥촥"]
tab=collections.defaultdict(lambda: collections.Counter()); secdur=collections.Counter(); secn=collections.Counter()
rows=[]
for vid,es in ev.items():
    cuts=p[vid]["cuts"]; W=p[vid]["words"]
    for s,e,n in sec[vid]: secdur[n]+=e-s; secn[n]+=1
    for k,x in enumerate(es):
        if x["peak"]<-30: continue            # 여운·잔향 제외
        t=x["s"]; typ=ty[f"{vid}|{k}"]
        if typ.startswith("기타"): typ="기타"
        n=next((n for s,e,n in sec[vid] if s-0.15<=t<e-0.15),sec[vid][-1][2])
        tab[n][typ]+=1
        dc=min([abs(t-c) for c in cuts] or [9])
        dw=min([abs(t-w["s"]) for w in W] or [9])
        rows.append(dict(vid=vid,t=t,typ=typ,sec=n,dcut=dc,dword=dw,dur=x["dur"],peak=x["peak"]))
json.dump(rows,open("rows.json","w",encoding="utf-8"),ensure_ascii=False)
names=sorted(secdur)
print("구간         편수 총길이  건수  초당  "+"  ".join(f"{m:>4s}" for m in MAIN+["기타"]))
for n in names:
    c=tab[n]; tot=sum(c.values())
    print(f"{n:8s} {secn[n]:4d} {secdur[n]:6.1f} {tot:5d} {tot/secdur[n]:5.2f}  "+"  ".join(f"{c[m]:4d}" for m in MAIN+["기타"]))
