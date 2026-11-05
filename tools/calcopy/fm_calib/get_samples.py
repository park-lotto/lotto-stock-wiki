# 표본 받기: 장부 같음 짝 30 + 같은 작가 다른 편 22 (360p 이하, 영상만)
import sys, json, subprocess, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
T = Path(r"C:/Users/CH/Desktop/로또의 주식/.tracks/칼카피엔진회원")
sys.path.insert(0, str(T))
from tools.calcopy import origin_find as OF
L = json.load(open(T / "channel/해외원본소재/원본찾기.json", encoding="utf-8"))
V = L["videos"]
D = Path("C:/t/fm_samples")
POS = [("yt:ZQphwE2W1Aw","ig:C5Bo8OfLGSr"),("yt:ZQphwE2W1Aw","tt:7364077204130565419"),("yt:ZQphwE2W1Aw","tt:7366547366083693856"),
 ("yt:h24TpkztzEE","ig:C9P0FPOtiiA"),("yt:h24TpkztzEE","ig:DDGNJSrpvlV"),("yt:h24TpkztzEE","tt:7390341317382999301"),("yt:h24TpkztzEE","yt:-esea89D1zc"),
 ("yt:DGW7r4kMXSM","ig:Ccm45TvpQyO"),("yt:8zFlDaqeeFI","ig:DCA7DchpuZd"),("yt:3zs52Z9qfrk","tt:7248656950156643610"),("yt:3zs52Z9qfrk","ig:DCA7DchpuZd"),
 ("yt:6owgrFC3xGU","ig:DHv7sK3iBCk"),("yt:6owgrFC3xGU","tt:7487315409926933782"),("yt:UksFATotbXA","tt:7024983137096600838"),("yt:LbwckRR8aBg","tt:7536957674399845654"),
 ("yt:Q7vTcbZUi1M","ig:DDfnOZiuO_o"),("yt:Q7vTcbZUi1M","yt:3QiGGQu7pO8"),("yt:Q7vTcbZUi1M","yt:Kp_ghhgpqGo"),("yt:Q7vTcbZUi1M","yt:QkyVg9Nrcio"),
 ("yt:ZX72TnDHc3o","yt:PnbnxovbDI4"),
 ("tt:7692354207281581334","tt:7390341317382999301"),("tt:7378766863334968594","tt:7487315409926933782"),("tt:7525703220321193217","tt:7248656950156643610"),
 ("ig:C7WCkrrvPTg","ig:Ccm45TvpQyO"),("ig:Dd-28c6IdGA","tt:7364077204130565419"),("yt:Ogq8vZrzKRc","tt:7390341317382999301"),("yt:3-ekGrr01GU","yt:PnbnxovbDI4"),
 ("yt:kaRFE8K0jUU","ig:C5Bo8OfLGSr"),("yt:HO4e9f0ilr8","ig:Ccm45TvpQyO"),("yt:cqczAbEZ3w8","tt:7487315409926933782")]
NEGCH = [("yt:ZQphwE2W1Aw","tt:7364077204130565419"),("yt:ZQphwE2W1Aw","tt:7366547366083693856"),("yt:6owgrFC3xGU","tt:7487315409926933782"),
 ("yt:Q7vTcbZUi1M","yt:3QiGGQu7pO8"),("yt:UksFATotbXA","tt:7024983137096600838"),("yt:ZX72TnDHc3o","yt:PnbnxovbDI4"),("yt:LbwckRR8aBg","tt:7536957674399845654"),
 ("yt:3zs52Z9qfrk","tt:7248656950156643610"),("yt:h24TpkztzEE","yt:-esea89D1zc"),("yt:h24TpkztzEE","tt:7390341317382999301"),("yt:Q7vTcbZUi1M","yt:QkyVg9Nrcio")]
def fn(key): return D / (key.replace(":", "_") + ".mp4")
def get(key, url=None):
    p = fn(key)
    if p.exists(): return p
    url = url or V[key]["url"]
    if shutil.disk_usage("C:/").free < 2.6e9:
        print("디스크 2.6GB 밑 — 멈춤", flush=True); return None
    try:
        subprocess.run(["yt-dlp", "-q", "--no-warnings", *OF.yt_auth(url), "-S", "res:360,+size", "-f", "bv*/b", "--max-filesize", "60M", "-o", str(p), url], capture_output=True, timeout=300)
    except Exception as e: print("err", key, e)
    return p if p.exists() else None
def lst(url, n=12):
    if "youtube.com" in url and "/shorts" not in url: url = url.rstrip("/") + "/shorts"
    r = subprocess.run(["yt-dlp", "--flat-playlist", "--no-warnings", *OF.yt_auth(url), "--playlist-end", str(n), "-J", url], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    try: j = json.loads(r.stdout)
    except Exception: return []
    return [(e.get("url") or e.get("webpage_url"), str(e.get("id")), e.get("duration")) for e in (j or {}).get("entries") or []]
keys = sorted({k for p in POS for k in p})
with ThreadPoolExecutor(4) as ex:
    got = dict(zip(keys, ex.map(get, keys)))
print("받음", sum(1 for v in got.values() if v), "/", len(keys), [k for k, v in got.items() if not v], flush=True)
import os
prev = json.load(open("C:/t/fm_jev/neg_acc.json",encoding="utf-8")) if os.path.exists("C:/t/fm_jev/neg_acc.json") else []
neg = [tuple(x) for x in prev]
for seed, okey in NEGCH:
    if sum(1 for x in neg if x[2]==okey) >= 4: continue
    o = V[okey]; oid = o["id"]; plat = okey.split(":")[0]
    k = 0
    for u, i, dur in lst(o["channel_url"]):
        if not u or i == oid or (dur and dur > 200): continue
        nk = f"{plat}:{i}"
        if get(nk, u):
            if (seed, nk, okey) not in neg: neg.append((seed, nk, okey))
            k += 1
        if k >= 4: break
    print("neg", okey, k, flush=True)
json.dump(neg, open("C:/t/fm_jev/neg_acc.json","w",encoding="utf-8"))
json.dump({"pos": [p for p in POS if got.get(p[0]) and got.get(p[1])], "neg": neg, "missing": [k for k, v in got.items() if not v]},
          open("C:/t/fm_jev/samples.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("끝", shutil.disk_usage("C:/").free / 1e9)
