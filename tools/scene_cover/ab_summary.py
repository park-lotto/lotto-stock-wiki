import json
def stats(res, only):
    t = dict(cells=0, freeze_cells=0, freeze_s=0.0, dup_in=0, cross=0, cuts=0, slow_cells=0)
    for jid in only:
        beats = res[jid]
        if isinstance(beats, dict): continue
        seen = []
        for b in beats:
            cs = b.get("c") or []
            if not cs or not b.get("t"): continue
            t["cells"] += 1; t["cuts"] += len(cs)
            fz = sum(max(0.0, c["d"] - c["sd"] * 1.2) for c in cs if c.get("sd"))
            if fz > 0.15: t["freeze_cells"] += 1
            t["freeze_s"] += fz
            if any(c.get("sd") and c["d"] / c["sd"] > 1.05 for c in cs): t["slow_cells"] += 1
            spans = [(c["v"], c["s"], c["s"] + (c["sd"] or c["d"])) for c in cs]
            dup = any(a[0] == b2[0] and a[1] < b2[2] + 0.3 and b2[1] < a[2] + 0.3 for i, a in enumerate(spans) for b2 in spans[i + 1:])
            if dup: t["dup_in"] += 1
            for sp in spans:
                if any(sp[0] == o[0] and sp[1] < o[2] - 0.2 and o[1] < sp[2] - 0.2 for o in seen): t["cross"] += 1
            seen += spans
    return t
o = json.load(open("/tmp/ab084_old.json")); n = json.load(open("/tmp/ab084_new.json"))
both = [j for j in n if j in o and not isinstance(n[j], dict) and not isinstance(o[j], dict)]
a, b = stats(o, both), stats(n, both)
print("공통 작업 %d · 칸 %d" % (len(both), a["cells"]))
for k, lab in [("freeze_cells", "멈춤 칸(0.15초 이상)"), ("freeze_s", "멈춘 초 합"), ("slow_cells", "느리게(1.05배↑) 칸"), ("dup_in", "한 칸 안 같은 장면 반복"), ("cross", "칸 넘어 같은 장면 다시"), ("cuts", "컷 수")]:
    print("  %-22s %8.1f → %8.1f" % (lab, a[k], b[k]))
