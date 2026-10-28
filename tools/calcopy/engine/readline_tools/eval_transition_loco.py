# -*- coding: utf-8 -*-
"""전환 분류 일반화 점검(LOCO) — 줄판독 눈 정답 전부로 '채널 하나 빼고 문턱 고르기 → 빠진 채널로 재기'.

dump: 편마다 프레임 배열(평균 밝기·자막 띠 뺀 선명도·프레임차·히스토그램차·검정/흰 비율·RGB 평균)과 정답(줄 t0·transition)을
      캐시(C:/숏템_칼카피/_readline_cache/tr/<slug>__<id>.npz)에 저장한다. 창·자막 띠는 eval_transition 과 같다.
loco: 컷 묶음(cutdet.cut_groups) → 특징(cutdet.classify_arrays) → 문턱 격자(G)를 훈련 채널로 고르고(미세 정확도 최대, 오탐 3% 넘으면 벌점)
      빠진 채널에서 일치·오탐을 잰다. --fixed 는 cutdet.V2 그대로 전 채널.
판정 주인은 cutdet.decide·classify_arrays — 이 도구는 문턱만 바꿔 부른다.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/eval_transition_loco.py dump kitchit:src itemhome:원본 ...
    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/eval_transition_loco.py loco [--fixed] [--write --labels "재표기 전|재표기 후"]
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine.readline_tools import cutdet  # noqa: E402
from tools.calcopy.engine.readline_tools.capseg import fps_filter  # noqa: E402

CACHE = Path(os.environ.get("READLINE_CACHE", "C:/숏템_칼카피/_readline_cache")) / "tr"
SPECIAL = ("zoomblur", "black", "flash")
G = dict(DIP=[0.5, 0.6, 0.7], REC=[0.7, 0.8], FLASH=[30.0, 40.0, 50.0], BLACK=[20.0, 30.0])   # LOCO 격자(측정 규칙 숫자 근처만)


def window_of(slug: str, vid: str):
    d = json.loads((ROOT / f"channel/{slug}/줄판독/{vid}.json").read_text(encoding="utf-8"))
    tp = ROOT / f"channel/{slug}/뜯기/{vid}/뜯기.json"
    tl = (json.loads(tp.read_text(encoding="utf-8")).get("layout") or {}) if tp.exists() else {}
    w = (d.get("layout") or {}).get("window")
    if not (isinstance(w, list) and len(w) == 4 and all(isinstance(v, (int, float)) for v in w)):
        w = tl.get("window")
    y0, y1 = (int(w[1]), min(1920, int(w[1] + w[3]))) if isinstance(w, list) and len(w) == 4 else (0, 1920)
    pf = ROOT / f"tools/calcopy/engine/readline_tools/profiles/{slug}.json"
    prof = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
    if prof.get("cutdet_window"):
        y0, y1 = prof["cutdet_window"]
    if y1 - y0 < 64:
        y0, y1 = 0, 1920
    c = tl.get("caption_band")
    cb = (c[0] - 20, c[1] + 20) if c else None
    gt = [(l["t0"], str(l.get("transition") or "none").split("(")[0]) for l in d["lines"]]
    return y0, y1, cb, gt


def dump_one(slug: str, mp4: str, vid: str) -> Path | None:
    out = CACHE / f"{slug}__{vid}.npz"
    if out.exists() or not os.path.exists(mp4):
        return None
    y0, y1, cb, gt = window_of(slug, vid)
    H = y1 - y0
    w, h = 360, int(H / 3)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", fps_filter(mp4) + f"crop=1080:{H}:0:{y0}:exact=1,scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    n = len(raw) // (w * h)
    F = np.frombuffer(raw, np.uint8)[:n * w * h].reshape(n, h, w)
    Ff = F.astype(np.float32)
    mean = Ff.mean((1, 2))
    sh = cutdet._masked_sharp(Ff, h, y0, cb)
    diff = np.r_[0, [np.abs(Ff[i] - Ff[i - 1]).mean((0, 1)) for i in range(1, n)]]
    hist = [cv2.calcHist([f], [0], None, [32], [0, 256]).ravel() for f in F]
    hist = [x / x.sum() for x in hist]
    hd = np.r_[0, [0.5 * np.abs(hist[i] - hist[i - 1]).sum() for i in range(1, n)]]
    r, g, b = cutdet.rgb_means(mp4, y0, y1)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, mean=mean, sh=sh, diff=diff, hd=hd, dark=(F < 20).mean((1, 2)), white=(F > 235).mean((1, 2)), std=Ff.std((1, 2)), r=r, g=g, b=b,
                        gt=json.dumps(gt, ensure_ascii=False), meta=json.dumps({"y0": y0, "y1": y1, "cb": cb, "n": int(n)}))
    return out


def load_items() -> list[tuple]:
    """정답 줄마다 (채널, 정답 종류, 가까운 사건 특징 목록) — 특징은 한 번만 뽑는다."""
    items = []
    for f in sorted(CACHE.glob("*.npz")):
        z = np.load(f)
        slug = f.stem.split("__")[0]
        n = len(z["mean"])
        A = {k: z[k] for k in ("mean", "sh", "dark", "white") if k in z.files}
        A["std"] = z["std"] if "std" in z.files else None
        m = min(n, len(z["r"]))
        for k in ("r", "g", "b"):
            A[k] = np.r_[z[k][:m], np.full(n - m, z[k][m - 1] if m else 0)]
        ev = cutdet.classify_arrays(A, cutdet.cut_groups(z["diff"], z["hd"]))
        for t, k in json.loads(str(z["gt"])):
            if k not in SPECIAL + ("cut",):
                continue
            near = [e for e in ev if (not e.get("start") and e["t"] - 0.15 <= t <= e.get("te", e["t"]) + 0.15) or (k != "cut" and t < 0.2 and e.get("start"))]
            near.sort(key=lambda e: abs(e["t"] - t))
            items.append((slug, k, near, f.stem, t))
    return items


def evaluate(items, P, slugs) -> dict:
    ch = defaultdict(lambda: [0, 0, 0, 0])
    for slug, k, near, vid, t in items:
        if slug not in slugs:
            continue
        p = None
        if near:
            e = near[0]
            p = cutdet.decide(e, P)
        c = ch[slug]
        if k != "cut":
            c[1] += 1
            c[0] += p == k
        elif p is not None:
            c[3] += 1
            c[2] += p != "cut"
    return ch


def _tot(ch):
    return [sum(x[i] for x in ch.values()) for i in range(4)]


def loco(items, fixed: bool = False) -> dict:
    chans = sorted(set(i[0] for i in items))
    combos = [dict(cutdet.V2)] if fixed else [dict(cutdet.V2, **dict(zip(G, v))) for v in itertools.product(*G.values())]
    rows = []
    for c in chans:
        if fixed:
            P = combos[0]
        else:
            best = None
            for P0 in combos:
                h, t, fp, n = _tot(evaluate(items, P0, set(chans) - {c}))
                o = h / max(1, t) - (10 * (fp / max(1, n) - 0.03) if fp / max(1, n) > 0.03 else 0)
                if best is None or o > best[0]:
                    best = (o, P0)
            P = best[1]
        x = evaluate(items, P, {c})[c]
        rows.append({"channel": c, "hit": x[0], "total": x[1], "fp": x[2], "cut_lines": x[3], "P": {k: P[k] for k in G}})
        print(rows[-1], flush=True)
    acc = [r["hit"] / r["total"] for r in rows if r["total"]]
    H, T, FP, N = (sum(r[k] for r in rows) for k in ("hit", "total", "fp", "cut_lines"))
    summ = {"channel_mean": round(float(np.mean(acc)), 3), "micro": f"{H}/{T}={H / max(1, T):.3f}", "fp": f"{FP}/{N}={FP / max(1, N):.3f}"}
    print(summ)
    return {"rows": rows, "summary": summ}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print(__doc__)
        return 2
    if a[0] == "dump":
        for spec in a[1:]:
            slug, src = spec.split(":")
            for f in sorted((ROOT / f"channel/{slug}/줄판독").glob("*.json")):
                if dump_one(slug, f"C:/숏템_칼카피/{slug}/{src}/{f.stem}.mp4", f.stem):
                    print(slug, f.stem, flush=True)
        return 0
    if a[0] == "loco":
        r = loco(load_items(), fixed="--fixed" in a)
        if "--write" in a:                                  # 표준 §11-8 ㊵: 채널마다 _kal/transition_loco.json{acc, fp} — acc≥0.90 ∧ fp≤3% 만 자동 단독
            import time
            for row in r["rows"]:
                acc = round(row["hit"] / row["total"], 3) if row["total"] else None
                fp = round(row["fp"] / row["cut_lines"], 3) if row["cut_lines"] else None
                d = {"acc": acc, "fp": fp, "hit": row["hit"], "total": row["total"], "fp_n": row["fp"], "cut_lines": row["cut_lines"],
                     "auto_ok": bool(acc is not None and acc >= 0.90 and fp is not None and fp <= 0.03) if acc is not None else bool(fp is not None and fp <= 0.03),
                     "mode": "fixed V2" if "--fixed" in a else "LOCO", "V2": dict(cutdet.V2), "labels": a[a.index("--labels") + 1] if "--labels" in a else "",
                     "made_by": "readline_tools/eval_transition_loco.py", "at": time.strftime("%Y-%m-%d %H:%M")}
                pth = ROOT / f"channel/{row['channel']}/_kal/transition_loco.json"
                pth.parent.mkdir(parents=True, exist_ok=True)
                pth.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
                print("→", pth)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
