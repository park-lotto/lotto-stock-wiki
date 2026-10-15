import json
def cnt(p):
    r = json.load(open(p)); a = b = n = 0
    for j, beats in r.items():
        if isinstance(beats, dict): continue
        for bb in beats:
            for c in bb.get("c") or []:
                n += 1
                if c["d"] < 0.8: a += 1
                if c["d"] < 1.2: b += 1
    return n, a, b
for m in ("old", "new"):
    n, a, b = cnt("/tmp/ab084_%s.json" % m)
    print("%s 컷 %d · 0.8초 미만 %d (%.0f%%) · 1.2초 미만 %d (%.0f%%)" % (m, n, a, 100.0 * a / n, b, 100.0 * b / n))
