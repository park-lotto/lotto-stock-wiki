# -*- coding: utf-8 -*-
"""원샷링크딸깍 — 완성본의 대사↔장면 맞음 측정(사장님 10-18 "대사에 맞는 편집포인트의 영상매칭이 안됐다").

    PYTHONUTF8=1 py tools/calcopy/oneshot/scene_fit.py <make 폴더> [<make 폴더> …]

make 폴더의 timeline.json(자막 조각 t0~t1) + final.mp4 → 조각마다 가운데 프레임 → material_auto.fit_judge(판단 주인)로 0~10점.
결과 = make/scene_fit.json + 화면 요약. 판정은 여기서 새로 하지 않는다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def measure(mk: Path, llm=None) -> dict:
    from tools.calcopy.engine import material_auto as MA
    mk = Path(mk)
    T = json.loads((mk / "timeline.json").read_text(encoding="utf-8"))
    lines = {}
    for p in T["pieces"]:
        lines.setdefault(p["line"], []).append(p["text"])
    gdir = mk / "fit"
    gdir.mkdir(exist_ok=True)
    items = []
    for k, p in enumerate(T["pieces"]):
        img = gdir / f"{k}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{(p['t0'] + p['t1']) / 2:.2f}", "-i", str(mk / "final.mp4"), "-frames:v", "1",
                        "-vf", "scale=-2:400", str(img)], stdin=subprocess.DEVNULL, capture_output=True)
        items.append({"img": str(img), "piece": p["text"], "line": " ".join(lines[p["line"]])})
    res = MA.fit_judge(items, mk, llm or MA.LLM(), tag="final")
    rows = [{"i": k, "piece": it["piece"], **r} for k, (it, r) in enumerate(zip(items, res))]
    sc = [r["score"] for r in rows if r.get("score") is not None]
    summ = {"n": len(rows), "judged": len(sc), "mean": round(sum(sc) / len(sc), 2) if sc else None,
            "below_min": sum(1 for s in sc if s < MA.FIT_MIN), "fit_min": MA.FIT_MIN}
    out = {"made_by": "tools/calcopy/oneshot/scene_fit.measure", "summary": summ, "rows": rows}
    (mk / "scene_fit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    for a in sys.argv[1:]:
        r = measure(Path(a))
        print("==", a, r["summary"])
        for x in r["rows"]:
            print(f"  {x['i']:2} {x.get('score')!s:>4} «{x['piece']}»  보임: {x.get('seen', x.get('why', ''))[:40]}  |  필요: {x.get('want', '')[:40]}")
