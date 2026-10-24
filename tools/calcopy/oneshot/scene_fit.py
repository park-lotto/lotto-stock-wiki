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


MAX_ITEMS = 30     # 시트 10칸 × 3회 = 편당 Claude 판정 ≤3회(관제 263 지시서 04 — 컷이 더 많으면 고르게 30개)


def render_items(work: Path, out_dir: Path) -> list[dict]:
    """공용 렌더러(render_bench) 산출 → 컷마다 {img, piece, line, cut} (컷 가운데 프레임 + 그 순간 자막 + 그 줄 전체 자막).
    입력 = work/render/timeline.json(cuts) · 자막표.json(rows) · final.mp4. 그림만 뽑는다(판정 안 함)."""
    R = Path(work) / "render"
    T = json.loads((R / "timeline.json").read_text(encoding="utf-8"))
    tab = json.loads((R / "자막표.json").read_text(encoding="utf-8"))
    rows = tab.get("rows") or []
    by_line = {}
    for r in rows:
        by_line.setdefault(r.get("line"), []).append(r.get("text") or "")
    cuts = list(T.get("cuts") or [])
    if len(cuts) > MAX_ITEMS:
        step = len(cuts) / MAX_ITEMS
        cuts = [cuts[int(k * step)] for k in range(MAX_ITEMS)]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for k, c in enumerate(cuts):
        mid = (float(c["t0"]) + float(c["t1"])) / 2
        img = out_dir / f"cut{k:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{mid:.2f}", "-i", str(R / "final.mp4"), "-frames:v", "1",
                        "-vf", "scale=-2:400", str(img)], stdin=subprocess.DEVNULL, capture_output=True)
        here = [r.get("text") or "" for r in rows if float(r["t0"]) <= mid < float(r["t1"])]
        items.append({"img": str(img), "piece": " ".join(here) or "(자막 없음)", "line": " ".join(by_line.get(c.get("line"), [])),
                      "cut": {"line": c.get("line"), "src": c.get("src"), "ss": c.get("ss"), "t0": c["t0"], "t1": c["t1"], "see": c.get("see")}})
    return items


def summarize(scores: list) -> dict:
    """점수 목록 → 평균·FIT_MIN 미만 수·비율(판단 주인 = material_auto.FIT_MIN)."""
    from tools.calcopy.engine import material_auto as MA
    sc = [s for s in scores if s is not None]
    return {"n": len(scores), "judged": len(sc), "mean": round(sum(sc) / len(sc), 2) if sc else None,
            "below_min": sum(1 for s in sc if s < MA.FIT_MIN), "below_rate": round(sum(1 for s in sc if s < MA.FIT_MIN) / len(sc), 3) if sc else None,
            "fit_min": MA.FIT_MIN}


def measure_render(work: Path, llm=None, out: Path | None = None) -> dict:
    """(render_bench 폴더 어댑터) 컷마다 대사↔장면 0~10 — 판정 = material_auto.fit_judge(Claude 소넷, 시트 10칸 1회).
    결과 = out(기본 work/render/scene_fit.json)."""
    from tools.calcopy.engine import material_auto as MA
    work = Path(work)
    gdir = work / "render" / "fit"
    items = render_items(work, gdir)
    llm = llm or MA.LLM()
    res = MA.fit_judge(items, work / "render", llm, tag="final")
    rows = [{"i": k, "piece": it["piece"], "cut": it["cut"], **r} for k, (it, r) in enumerate(zip(items, res))]
    o = {"made_by": "tools/calcopy/oneshot/scene_fit.measure_render", "summary": summarize([r.get("score") for r in rows]), "rows": rows,
         "calls": len(getattr(llm, "calls", None) or [])}
    dst = Path(out) if out else work / "render" / "scene_fit.json"
    dst.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    return o


if __name__ == "__main__":
    for a in sys.argv[1:]:
        r = measure(Path(a))
        print("==", a, r["summary"])
        for x in r["rows"]:
            print(f"  {x['i']:2} {x.get('score')!s:>4} «{x['piece']}»  보임: {x.get('seen', x.get('why', ''))[:40]}  |  필요: {x.get('want', '')[:40]}")
