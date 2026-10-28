import json,sys,numpy as np
sys.stdout.reconfigure(encoding="utf-8")
rows=json.load(open("rows.json",encoding="utf-8")); p=json.load(open("prep.json",encoding="utf-8")); cap=json.load(open("capchg.json"))
rng=np.random.default_rng(0)
def near(t,arr,tol=0.08): return any(abs(t-a)<=tol for a in arr)
def cls(r,t):
    c=near(t,p[r["vid"]]["cuts"]); k=near(t,cap[r["vid"]])
    return c,k
print("종류   건수 | 컷   | 자막교체 | 컷∪자막 | 둘다아님   (실제% / 대조%)")
for typ in ["뽁","둥","띠링","휙","틱","딸깍2","촥촥","기타"]:
    R=[r for r in rows if r["typ"]==typ and r["sec"]!="1제목훅"]
    a=np.array([cls(r,r["t"]) for r in R]); b=[]
    for _ in range(30):
        for r in R: b.append(cls(r,r["t"]+rng.choice([-1,1])*rng.uniform(0.4,1.5)))
    b=np.array(b)
    f=lambda m:(m[:,0].mean()*100,m[:,1].mean()*100,(m[:,0]|m[:,1]).mean()*100)
    x,y=f(a),f(b)
    print(f"{typ:5s} {len(R):4d} | {x[0]:3.0f}/{y[0]:2.0f} | {x[1]:3.0f}/{y[1]:2.0f}   | {x[2]:3.0f}/{y[2]:2.0f}  | {100-x[2]:3.0f}")
# 자막 교체 중 소리가 붙은 비율
tot=hit=0
for vid,cs in cap.items():
    ts=[r["t"] for r in rows if r["vid"]==vid]
    for c in cs:
        if c<1.5: continue
        tot+=1; hit+=near(c,ts)
print(f"\n자막 교체 {tot}번 중 ±80ms 안에 효과음 있음: {hit} ({hit/tot*100:.0f}%)")
tot=hit=0
for vid in p:
    ts=[r["t"] for r in rows if r["vid"]==vid]
    for c in p[vid]["cuts"]:
        tot+=1; hit+=near(c,ts)
print(f"컷 {tot}번 중 ±80ms 안에 효과음 있음: {hit} ({hit/tot*100:.0f}%)")
