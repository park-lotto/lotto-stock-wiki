import json,sys,collections
sys.stdout.reconfigure(encoding="utf-8")
rows=json.load(open("rows.json",encoding="utf-8")); sec=json.load(open("sections.json",encoding="utf-8")); p=json.load(open("prep.json",encoding="utf-8"))
by=collections.defaultdict(list)
for r in rows: by[r["vid"]].append(r)
for name in ["1제목훅","2떡밥","3정체공개","4기능시연","5반전","6마무리"]:
    print(f"\n■ {name} 시작점 ±0.35초 안의 소리 (시작 기준 상대초)")
    for vid in sec:
        b=[x for x in sec[vid] if x[2]==name]
        if not b: continue
        s=b[0][0]
        near=[f'{r["typ"]}{r["t"]-s:+.2f}' for r in by[vid] if -0.35<=r["t"]-s<=0.35]
        cut=[f"{c-s:+.2f}" for c in p[vid]["cuts"] if abs(c-s)<=0.35]
        print(f"  {vid}  {' '.join(near) or '(없음)':40s} 컷:{' '.join(cut) or '-'}")
print("\n■ 영상 맨 끝 1.5초")
for vid in sec:
    d=p[vid]["dur"]; print(f"  {vid} 길이{d:.1f}  ", " ".join(f'{r["typ"]}@-{d-r["t"]:.2f}' for r in by[vid] if d-r["t"]<=1.5))
