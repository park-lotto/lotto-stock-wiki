# 같음/다름 표본으로 frame_match 꼴 바꿔 재기 — 짝마다 씨앗 프레임별 최고 상관(best)을 꼴마다 저장
import json, subprocess, sys, numpy as np, cv2
from pathlib import Path
D = Path("C:/t/fm_samples"); OUT = Path("C:/t/fm_jev/best"); OUT.mkdir(exist_ok=True)
def frames(p, fps, h=180):
    pr = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height:format=duration","-of","json",str(p)],capture_output=True,text=True)
    j = json.loads(pr.stdout); st = j["streams"][0]; dur = float(j["format"].get("duration") or 0)
    if dur > 150: fps = min(fps, 2.0)
    w = max(2, int(round(st["width"]*h/st["height"]/2))*2)
    r = subprocess.run(["ffmpeg","-v","error","-i",str(p),"-vf",f"fps={fps},scale={w}:{h}","-f","rawvideo","-pix_fmt","gray","-"],capture_output=True)
    a = np.frombuffer(r.stdout,np.uint8)
    return a.reshape(-1,h,w).astype(np.float32)
def sig(c):
    v = cv2.resize(c,(32,32),interpolation=cv2.INTER_AREA).ravel(); v = v-v.mean(); n = np.linalg.norm(v)
    return v/n if n>1e-6 else v
REG = {"cur": (.1,.9,.40,.80), "wide": (.05,.95,.20,.80), "mid": (.25,.75,.45,.65)}
def cand_sigs(C, asp, zooms, nx, ny=9):
    Hc, Wc = C.shape[1:]; out = []
    for z in zooms:
        cw = int(.8*Wc/z); ch = int(cw/asp)
        if ch > Hc: ch = Hc; cw = int(ch*asp)
        if cw < 8 or ch < 8: continue
        xs = [(Wc-cw)//2] if nx == 1 else np.linspace(0, Wc-cw, nx).astype(int)
        for xo in xs:
            for yo in np.linspace(0, Hc-ch, ny).astype(int):
                for f in C:
                    c = f[yo:yo+ch, xo:xo+cw]; out.append(sig(c)); out.append(sig(c[:, ::-1]))
    return np.stack(out) if out else None
def best_of(ss, cs):
    b = np.full(len(ss), -1.0, np.float32)
    for i in range(0, len(cs), 20000):
        b = np.maximum(b, (ss @ cs[i:i+20000].T).max(1))
    return b
VAR = {"cur": ("cur", (1.0,1.2,1.4), 1), "cur+x": ("cur", (1.0,1.2,1.4), 5), "cur+xz": ("cur", (0.8,1.0,1.2,1.4,1.7,2.0), 5),
       "wide+xz": ("wide", (0.8,1.0,1.2,1.4,1.7,2.0), 5), "mid+xz": ("mid", (0.8,1.0,1.2,1.4,1.7,2.0), 5)}
def run(pairs):
    cache = {}
    def F(k, fps):
        key = (k, fps)
        if key not in cache: cache[key] = frames(k if isinstance(k, Path) else D/(k.replace(":","_")+".mp4"), fps)
        return cache[key]
    for tag, sk, ck in pairs:
        o = OUT/f"{tag}.npz"
        if o.exists(): continue
        try:
            S, C = F(sk, 1.0), F(ck, 4.0)
        except Exception as e:
            print(tag, "영상 못 읽음(건너뜀)", type(e).__name__, flush=True); continue
        Hs, Ws = S.shape[1:]; res = {}
        for vn, (rg, zs, nx) in VAR.items():
            x0,x1,y0,y1 = REG[rg]; X0,X1,Y0,Y1 = int(x0*Ws),int(x1*Ws),int(y0*Hs),int(y1*Hs)
            ss = np.stack([sig(f[Y0:Y1, X0:X1]) for f in S]); cs = cand_sigs(C, (X1-X0)/(Y1-Y0), zs, nx)
            res[vn] = best_of(ss, cs)
        np.savez(o, **res, seed_n=len(S), cand_n=len(C))
        print(tag, {k: round(float((v>=.8).mean()),3) for k, v in res.items()}, flush=True)
        if len(cache) > 12: cache.clear()
if __name__ == "__main__":
    sm = json.load(open("C:/t/fm_jev/samples.json", encoding="utf-8")); neg = json.load(open("C:/t/fm_jev/neg_acc.json", encoding="utf-8"))
    P = [(f"pos_{i:02d}", a, b) for i, (a, b) in enumerate(sm["pos"])]
    N = [(f"neg_{i:02d}", s, n) for i, (s, n, o) in enumerate(neg)]
    K = Path("C:/t/kal_snap")
    X = [("snapneg_B", K/"origin/work_ig/h3RPb5yZ9Ew/seed/v.mp4", K/"material/origin_DeaeUEbzy6E.mp4"),
         ("snapneg_C", K/"data/snapbwatni/src/CZdHXV0nfGw.mp4", K/"material/origin_DeaeUEbzy6E.mp4"),
         ("snappos_U", K/"out/숏템스냅_남대문스카프_1차.mp4", K/"material/origin_DeaeUEbzy6E.mp4")]
    sel = sys.argv[1] if len(sys.argv) > 1 else "all"
    run([x for x in P+N+X if sel == "all" or x[0].startswith(sel)])
