# -*- coding: utf-8 -*-
"""1차 분석 집계 — judge(제미니 판독)·asr(받아쓰기)·bench(숫자 자)를 편마다 묶고 갈래별로 센다.

    PYTHONUTF8=1 py tools/calcopy/summarize50.py C:/숏템_칼카피/sseolpulda channel/sseolpulda

출력: <out>/1차분석_편별.json (편마다 한 줄) · <out>/1차분석_갈래.json (갈래별 집계)
갈래 이름은 판독이 자유롭게 붙인 것 — 사람 확정 전 '제안'이다.
"""
from __future__ import annotations

import collections
import json
import statistics as st
import sys
from pathlib import Path


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 2) if xs else None


def main(base: str, out: str):
    base, out = Path(base), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    top = {v["id"]: v for v in json.loads((base / "top50.json").read_text(encoding="utf-8"))}
    bench = json.loads((base / "bench_main" / "bench.json").read_text(encoding="utf-8"))
    pv = bench["per_video"]
    rows = []
    for vid, meta in top.items():
        j = base / "judge" / f"{vid}.json"
        J = json.loads(j.read_text(encoding="utf-8")) if j.exists() else {}
        a = base / "asr" / f"{vid}.json"
        words = []
        if a.exists():
            words = [w for w in json.loads(a.read_text(encoding="utf-8")).get("results", []) if w.get("type") == "word"]
        spoken = sum(w["end_time"] - w["start_time"] for w in words)
        chars = sum(len(w["alternatives"][0]["content"]) for w in words)
        b = pv.get(vid, {})
        cuts = (b.get("cuts") or {})
        rows.append({
            "id": vid, "views": meta["views"], "title": meta["title"],
            "style": J.get("style"), "voice": (J.get("voice") or {}).get("kind"),
            "gender": (J.get("voice") or {}).get("gender"), "roles": (J.get("voice") or {}).get("roles"),
            "honorific": (J.get("tone") or {}).get("honorific"),
            "hook": (J.get("hook") or {}).get("text"),
            "beats": [x.get("fn") for x in (J.get("beats") or [])],
            "n_effects": len(J.get("effects") or []), "n_sfx": len(J.get("sfx") or []),
            "n_sfx_alone": sum(1 for s in (J.get("sfx") or []) if s.get("alone")),
            "effect_kinds": collections.Counter(e.get("kind") for e in (J.get("effects") or [])),
            "duration": (b.get("probe") or {}).get("duration"),
            "frame_variant": b.get("variant"),
            "n_cuts": len(cuts.get("cuts") or []) if isinstance(cuts.get("cuts"), list) else None,
            "first_word": words[0]["start_time"] if words else None,
            "cps": round(chars / spoken, 2) if spoken else None,
            "judged": bool(J),
        })
    (out / "1차분석_편별.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=dict), encoding="utf-8")
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["style"] or "(판독 없음)"].append(r)
    agg = []
    for name, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        ek = collections.Counter()
        for r in rs:
            ek.update(r["effect_kinds"])
        agg.append({
            "style": name, "n": len(rs), "views_median": int(st.median(r["views"] for r in rs)),
            "views_max": max(r["views"] for r in rs),
            "voice": collections.Counter(r["voice"] for r in rs).most_common(),
            "honorific": collections.Counter(r["honorific"] for r in rs).most_common(),
            "duration_median": _med([r["duration"] for r in rs]),
            "cps_median": _med([r["cps"] for r in rs]), "first_word_median": _med([r["first_word"] for r in rs]),
            "cuts_median": _med([r["n_cuts"] for r in rs]),
            "effects_per_video": _med([r["n_effects"] for r in rs]), "effect_kinds": ek.most_common(8),
            "sfx_per_video": _med([r["n_sfx"] for r in rs]),
            "frame_variants": collections.Counter(r["frame_variant"] for r in rs).most_common(),
            "beat_shapes": collections.Counter(" > ".join(r["beats"]) for r in rs).most_common(3),
            "ids": [r["id"] for r in rs],
        })
    (out / "1차분석_갈래.json").write_text(json.dumps(agg, ensure_ascii=False, indent=1), encoding="utf-8")
    for g in agg:
        print(f"{g['n']:>2}편 중앙 {g['views_median']:>9,} | {g['style']} | 목소리 {g['voice'][:2]} | 길이 {g['duration_median']} | 틀 {g['frame_variants'][:3]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
