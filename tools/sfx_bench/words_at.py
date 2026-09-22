import json,sys
sys.stdout.reconfigure(encoding="utf-8")
rows=json.load(open("rows.json",encoding="utf-8")); p=json.load(open("prep.json",encoding="utf-8")); cap=json.load(open("capchg.json"))
def phrase(vid,t):
    cs=sorted(cap[vid]); nxt=next((c for c in cs if c>t+0.1),t+1.2)
    return " ".join(w["w"] for w in p[vid]["words"] if t-0.15<=w["s"]<nxt-0.1)
for typ in sys.argv[1:]:
    print(f"\n■ {typ}")
    for r in rows:
        if r["typ"]==typ and r["sec"]!="1제목훅" and any(abs(r["t"]-c)<=0.08 for c in cap[r["vid"]]):
            print(f'  {r["sec"]:6s} {r["peak"]:6.1f}dB | {phrase(r["vid"],r["t"])}')
