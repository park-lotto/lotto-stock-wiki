import json
n = json.load(open("/tmp/ab084_new.json"))
from collections import Counter
kind = Counter(); ex = []
for j, beats in n.items():
    if isinstance(beats, dict): continue
    for i, b in enumerate(beats):
        cs = b.get("c") or []
        sp = [(c["v"], c["s"], c["s"] + (c["sd"] or c["d"])) for c in cs]
        for x in range(len(sp)):
            for y in range(x + 1, len(sp)):
                a, bb = sp[x], sp[y]
                if a[0] != bb[0] or not (a[1] < bb[2] + 0.3 and bb[1] < a[2] + 0.3): continue
                ov = min(a[2], bb[2]) - max(a[1], bb[1])
                k = "겹침(진짜 반복)" if ov > 0.05 else "원본에서 바로 이어짐(다른 장면)"
                kind[k] += 1
                if ov > 0.05 and len(ex) < 6: ex.append((j[:8], i, sp))
print(kind)
for e in ex: print(e)
