# 혼동표: 꼴(VAR) × 문턱 × 판정식
import json, glob, numpy as np, itertools
from pathlib import Path
R = []
for f in sorted(glob.glob("C:/t/fm_jev/best/*.npz")):
    z = np.load(f); tag = Path(f).stem
    if tag.startswith("pos_") and int(tag[4:]) >= 20: continue
    R.append((tag, "pos" in tag, {k: z[k] for k in z.files if k not in ("seed_n", "cand_n")}, int(z["seed_n"]), int(z["cand_n"])))
def longest(m):
    b = c = 0
    for x in m:
        c = c + 1 if x else 0; b = max(b, c)
    return b
def metr(best, thr, cand_s):
    m = best >= thr
    return {"share": m.mean(), "run": longest(m), "cnt": int(m.sum()), "share_min": m.sum() / max(1, min(len(best), cand_s))}
RULES = {"share>=.25": lambda x: x["share"] >= .25, "run>=2": lambda x: x["run"] >= 2, "run>=3": lambda x: x["run"] >= 3, "run>=4": lambda x: x["run"] >= 4,
         "cnt>=3": lambda x: x["cnt"] >= 3, "cnt>=5": lambda x: x["cnt"] >= 5, "share_min>=.25": lambda x: x["share_min"] >= .25, "share_min>=.4": lambda x: x["share_min"] >= .4}
out = []
for v in R[0][2]:
    for thr in (.7, .75, .8, .85, .9):
        M = [(t, p, metr(b[v], thr, cn / 4)) for t, p, b, sn, cn in R]
        for rn, fn in RULES.items():
            tp = sum(1 for t, p, x in M if p and fn(x)); fn_ = sum(1 for t, p, x in M if p and not fn(x))
            fp = sum(1 for t, p, x in M if not p and fn(x)); tn = sum(1 for t, p, x in M if not p and not fn(x))
            out.append({"var": v, "thr": thr, "rule": rn, "TP": tp, "FN": fn_, "FP": fp, "TN": tn})
out.sort(key=lambda r: (r["FP"] > 0, -r["TP"], r["FP"]))
print("총 같음", sum(p for _, p, *_ in R), "다름", sum(not p for _, p, *_ in R))
for r in out[:25]: print(r)
cur = [r for r in out if r["var"] == "cur" and r["thr"] == .8 and r["rule"] == "share>=.25"]; print("현재 꼴:", cur)
json.dump(out, open("C:/t/fm_jev/fm_table_seedpairs.json", "w"), indent=0)
# 짝별 숫자(가장 나은 꼴 보려고)
for t, p, b, sn, cn in R:
    print(t, {v: (round(float(b[v].max()), 2), metr(b[v], .8, cn / 4)["run"], metr(b[v], .8, cn / 4)["cnt"]) for v in b}, sn, cn)
