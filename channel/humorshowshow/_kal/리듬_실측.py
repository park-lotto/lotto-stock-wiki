# 썰템쇼 판 리듬 4칸 실측 — 벤치 6편 원본(media_of = 관문·재현과 같은 자) + 줄판독(kal_analyze._decorated = placement._is_deco 와 같은 칸)
import json, re, statistics, sys
from pathlib import Path
sys.path.insert(0, ".")
from tools.calcopy.engine import kal_analyze as K

SRC = Path("C:/숏템_칼카피/humorshowshow/mp4")
LR = Path("channel/humorshowshow/줄판독")
PHOTO = re.compile(r"사진|화보|정지 ?(화면|그림|이미지)|캡처|스크린샷|이미지")
out = {}
for f in sorted(LR.glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    vid = d["id"]
    m = K.media_of(str(SRC / f"{vid}.mp4"))
    hook = sum(1 for t in m["cut_at"] if 0.1 <= t <= 3.0)
    lines = [l for l in d.get("lines") or [] if isinstance(l, dict)]
    plain = 0
    for l in lines:
        D = K._decorated(l)
        if not (D["enter_fx"] or D["emph"] or D["sticker"] or D["variant"]):
            plain += 1
    ph = 0.0
    hits = []
    for l in lines:
        txt = " ".join(str(l.get(k) or "") for k in ("scene", "scene_desc", "notes"))
        if PHOTO.search(txt):
            ph += float(l.get("t1") or 0) - float(l.get("t0") or 0)
            hits.append([l.get("t0"), l.get("t1"), txt[:80]])
    dur = float(d.get("dur") or m["duration"])
    out[vid] = {"dur": dur, "cut_median": m["cut_median"], "n_cuts": m["n_cuts"], "hook_cuts_3s": hook,
                "lines": len(lines), "plain": plain, "plain_share": round(plain / len(lines), 3) if lines else None,
                "photo_s": round(ph, 2), "photo_share": round(ph / dur, 3), "photo_hits": hits}
    print(vid, json.dumps({k: v for k, v in out[vid].items() if k != "photo_hits"}, ensure_ascii=False), flush=True)
cm = [v["cut_median"] for v in out.values()]
hk = [v["hook_cuts_3s"] for v in out.values()]
P = sum(v["plain"] for v in out.values()); N = sum(v["lines"] for v in out.values())
ps = [v["photo_share"] for v in out.values()]
summ = {"cut_median": {"median": statistics.median(cm), "min": min(cm), "max": max(cm)},
        "hook_cuts_3s": {"median": statistics.median(hk), "min": min(hk)},
        "plain_share": {"pooled": round(P / N, 3), "P": P, "N": N, "per": [v["plain_share"] for v in out.values()]},
        "photo_share": {"median": statistics.median(ps), "max": max(ps), "p75": round(statistics.quantiles(ps, n=4, method="inclusive")[2], 3)}}
print(json.dumps(summ, ensure_ascii=False, indent=1))
Path(sys.argv[1]).write_text(json.dumps({"per": out, "summary": summ}, ensure_ascii=False, indent=1), encoding="utf-8")
