import json,sys,numpy as np,soundfile as sf,collections,random
from scipy.signal import fftconvolve
sys.stdout.reconfigure(encoding="utf-8")
rows=json.load(open("rows.json",encoding="utf-8")); p=json.load(open("prep.json",encoding="utf-8")); cap=json.load(open("capchg.json"))
SR=44100; X={v:sf.read(f"sep/htdemucs/{v}/nv.wav")[0] for v in p}
def near(t,arr,tol=0.08): return any(abs(t-a)<=tol for a in arr)
def seg(r): a=int(r["t"]*SR); return X[r["vid"]][max(0,a-441):a+int(0.3*SR)]
def wx(a,b):
    a=a/(np.linalg.norm(a)+1e-9); b=b/(np.linalg.norm(b)+1e-9); return float(np.abs(fftconvolve(a,b[::-1],"full")).max())
random.seed(1)
for typ in ["뽁","촥촥","기타"]:
    for lab,flt in [("자막자리",True),("자막밖",False)]:
        R=[r for r in rows if r["typ"]==typ and r["sec"]!="1제목훅" and near(r["t"],cap[r["vid"]])==flt]
        pr=[(a,b) for i,a in enumerate(R) for b in R[i+1:] if a["vid"]!=b["vid"]]; random.shuffle(pr); pr=pr[:80]
        if pr: print(f"{typ} {lab} {len(R)}건: 다른 영상끼리 파형일치 중앙 {np.median([wx(seg(a),seg(b)) for a,b in pr]):.2f}")
# 자막 교체마다: 붙은 소리 / 새 문장 시작 여부 / 컷 동반
tab=collections.defaultdict(collections.Counter)
for vid,cs in cap.items():
    starts=[s["s"] for s in p[vid]["segs"]]
    for c in cs:
        if c<1.5: continue
        R=[r for r in rows if r["vid"]==vid and abs(r["t"]-c)<=0.08 and r["typ"]!="촥촥"]
        typ="+".join(sorted(set(r["typ"] for r in R))) or "(무음)"
        sent="새문장" if near(c,starts,0.35) else "문장중간"
        cut="컷동반" if near(c,p[vid]["cuts"]) else "컷없음"
        tab[(sent,cut)][typ]+=1
for k,c in sorted(tab.items()):
    n=sum(c.values()); print(f"\n[{k[0]}·{k[1]}] {n}번:", ", ".join(f"{t} {v}({v/n*100:.0f}%)" for t,v in c.most_common(7)))
