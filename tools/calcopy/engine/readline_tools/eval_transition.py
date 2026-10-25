# -*- coding: utf-8 -*-
"""전환 종류 점검(eval_transition) — cutdet --v2 가 줄판독(눈으로 고친 정답)의 transition 칸과 얼마나 맞나.

정답 = channel/<slug>/줄판독/<편>.json 줄의 transition 이 zoomblur/black/flash 인 줄(컷 묶음 [시작−0.15, 끝+0.15] 안, 영상 시작 줄은 start 사건) +
       transition=cut 인 줄을 특수 전환으로 잘못 본 수(오탐).
창 = 줄판독 layout.window 세로, 자막 띠(빼기) = 뜯기 layout.caption_band ±20.
10-25 실측(키치잇 8편): 특수 전환 12/13 일치(92.3%) · cut 57줄 중 오탐 0 — 남은 1곳은 BRa 0.80 flash 를 zoomblur 로 봄(옛 분류도 같음).

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/eval_transition.py <slug> --src-dir C:/숏템_칼카피/<slug>/src [--ids a,b]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine.readline_tools import cutdet  # noqa: E402

SPECIAL = ("zoomblur", "black", "flash")


def eval_video(slug: str, vid: str, mp4: str) -> dict:
    d = json.loads((ROOT / f"channel/{slug}/줄판독/{vid}.json").read_text(encoding="utf-8"))
    tp = ROOT / f"channel/{slug}/뜯기/{vid}/뜯기.json"
    tl = (json.loads(tp.read_text(encoding="utf-8")).get("layout") or {}) if tp.exists() else {}
    w = (d.get("layout") or {}).get("window")
    if not (isinstance(w, list) and len(w) == 4 and all(isinstance(v, (int, float)) for v in w)):
        w = tl.get("window")                                  # 줄판독에 창이 없으면 뜯기 창
    y0, y1 = (int(w[1]), min(1920, int(w[1] + w[3]))) if isinstance(w, list) and len(w) == 4 else (0, 1920)
    c = tl.get("caption_band")
    cb = (c[0] - 20, c[1] + 20) if c else None
    pf = ROOT / f"tools/calcopy/engine/readline_tools/profiles/{slug}.json"
    prof = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
    if prof.get("cutdet_window"):
        y0, y1 = prof["cutdet_window"]
    r = cutdet.cutdet(mp4, y0, y1, v2=True, cap_band=cb, motion=False)
    rows, hit, tot, fp, ncut = [], 0, 0, 0, 0
    for l in d["lines"]:
        g = str(l.get("transition") or "none").split("(")[0]
        if g in SPECIAL:
            tot += 1
            near = sorted([c for c in r["cuts"] if c["t"] - 0.15 <= l["t0"] <= c.get("t_end", c["t"]) + 0.15 or (l["t0"] < 0.2 and c.get("start"))],
                          key=lambda c: abs(c["t"] - l["t0"]))
            k = near[0]["kind"] if near else None
            hit += k == g
            rows.append({"t0": l["t0"], "정답": g, "도구": k, "옛": near[0].get("kind_v1") if near else None,
                         **({k2: near[0].get(k2) for k2 in ("dip_ratio", "blur_tail", "border")} if near else {})})
        elif g == "cut":
            near = sorted([c for c in r["cuts"] if c["t"] - 0.15 <= l["t0"] <= c.get("t_end", c["t"]) + 0.15], key=lambda c: abs(c["t"] - l["t0"]))
            if near:
                ncut += 1
                if near[0]["kind"] != "cut":
                    fp += 1
                    rows.append({"t0": l["t0"], "정답": "cut", "도구": near[0]["kind"], "옛": near[0].get("kind_v1"),
                                 **{k2: near[0].get(k2) for k2 in ("dip_ratio", "blur_tail", "border")}})
    return {"id": vid, "hit": hit, "total": tot, "fp": fp, "cut_lines": ncut, "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--src-dir", required=True)
    ap.add_argument("--ids")
    A = ap.parse_args(argv)
    ids = A.ids.split(",") if A.ids else sorted(p.stem for p in (ROOT / f"channel/{A.slug}/줄판독").glob("*.json"))
    H = T = F = N = 0
    for vid in ids:
        e = eval_video(A.slug, vid, str(Path(A.src_dir) / f"{vid}.mp4"))
        H += e["hit"]; T += e["total"]; F += e["fp"]; N += e["cut_lines"]
        for x in e["rows"]:
            print(vid, x)
    print(f"특수 전환 일치 {H}/{T} = {H / max(1, T):.3f} · cut 줄 오탐 {F}/{N}")
    return 0 if T == 0 or H / T >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
