"""강의 후보 전부의 한국어 자막을 subs/ 에 받아 둔다(fidelity.subs 재사용). 실행: py -I fetch_subs.py"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fidelity import subs
vids = json.load(open(os.path.join(HERE, "videos.json"), encoding="utf-8"))
cand = sorted([v for v in vids.values() if 240 <= v["duration"] <= 5400 and v["views"] >= 3000], key=lambda v: (-len(v["queries"]), -v["views"]))
n = 0
for i, v in enumerate(cand):
    t = subs(v["id"]); n += bool(t)
    print(f"{i + 1}/{len(cand)} 자막 {'O' if t else 'X'} {len(t)}자 {v['title'][:30]}", flush=True)
print("자막 있음", n, "/", len(cand))
