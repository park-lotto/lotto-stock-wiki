# 짧은 딸깍/반짝(고역 순간 솟음) 찾기 + 자막 교체·컷 표식과 맞물림(우연 기대 같이)
import sys, json, subprocess, numpy as np
from scipy.signal import stft, find_peaks
from scipy.ndimage import median_filter
W = "C:/숏템_칼카피/evenshopping/work"
res = {}
for vid in sys.argv[1:]:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", f"C:/숏템_칼카피/evenshopping/src/{vid}.mp4", "-ac", "1", "-ar", "44100", "-f", "s16le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768
    f, t, Z = stft(x, 44100, nperseg=512, noverlap=512 - 128)
    P = np.abs(Z) ** 2 + 1e-12
    m = (f >= 9000) & (f <= 18000)
    hf = 10 * np.log10(P[m].sum(0))
    ex = hf - median_filter(hf, size=int(0.4 / (t[1] - t[0])) | 1, mode="nearest")
    pk, pr = find_peaks(ex, height=12, distance=int(0.12 / (t[1] - t[0])))
    ev = []
    for p in pk:
        a = p
        while a > 0 and ex[a - 1] > 6: a -= 1
        b = p
        while b < len(ex) - 1 and ex[b + 1] > 6: b += 1
        ev.append({"t": round(float(t[p]), 3), "db": round(float(ex[p]), 1), "dur": round(float((b - a + 1) * (t[1] - t[0])), 3)})
    mj = json.load(open(f"{W}/{vid}/m.json", encoding="utf-8"))
    caps = [s["t0"] for s in mj["segs"][1:]]
    cuts = [c["t"] for c in mj["cuts"]]
    dur = mj["dur"]
    near = lambda tt, arr, tol=0.06: any(abs(tt - a) <= tol for a in arr)
    rng = np.random.default_rng(0); rt = rng.uniform(0, dur, 4000)
    strong = [e for e in ev if e["db"] >= 18]
    res[vid] = {"n_ev": len(ev), "n_strong": len(strong),
                "strong_at_cap": sum(near(e["t"], caps) for e in strong), "strong_at_cut": sum(near(e["t"], cuts) for e in strong),
                "chance_cap": round(float(np.mean([near(a, caps) for a in rt])), 3), "chance_cut": round(float(np.mean([near(a, cuts) for a in rt])), 3),
                "caps_with_click": sum(near(c, [e["t"] for e in strong]) for c in caps), "n_caps": len(caps),
                "dur_med": float(np.median([e["dur"] for e in strong])) if strong else None, "strong": strong}
    print(vid, {k: v for k, v in res[vid].items() if k != "strong"})
json.dump(res, open(f"{W}/click_detect.json", "w"), indent=0)
