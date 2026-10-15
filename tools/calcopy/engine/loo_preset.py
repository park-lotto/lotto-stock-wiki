# -*- coding: utf-8 -*-
"""하위 스타일 프리셋 만들기 + 하나 빼고 재현(leave-one-out) 검증.

    PYTHONUTF8=1 py tools/calcopy/engine/loo_preset.py --slug sseolpulda --style A_흰바탕창/창안_흰외곽선 \
        --frames <편별 to_frame 결과 폴더(frame_<id>.json)> --ids ho5GSd-4To0 7DYbxVNz5q8 1_VtwOkbbVE --out <작업 폴더> [--no-loo]

1) 하위 스타일 프리셋(channel/<slug>/preset/<style>) — 그 편들만으로(평균 내지 않는다, 사장님 10-16).
   자막 층은 분석기 결함(D9: 창 안 자막을 제목으로 읽음)이 고쳐지기 전이라 bench 자막 측정(bench_one.measure: 첫 줄 y·줄 높이·
   극성·외곽선)으로 **임시** 층을 만들어 넣는다(글꼴은 모름 → CcPretendard-Bold, made_from.notes 에 '임시').
2) 편 하나씩 빼고 나머지로 프리셋을 만들어, 뺀 편의 제목 글자·재료만 넣고 기본값+관계 규칙(apply --defaults)으로 설명서 →
   frame_video --src-window 로 렌더(자막 글은 비움 — 재료 창 안에 원본 자막이 박혀 있어 자막 항목은 어차피 무효) → compare.
   결과 loo.json · loo.md(틀 항목 표).
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import statistics as st
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import preset_save as P  # noqa: E402

TEMP_CAP_FONT = "CcPretendard-Bold"
FRAME_KEYS = ("frame.window", "frame.bg_rgb", "frame.band_count", "band.line_h", "band.stroke", "band.ink")


TTEUTGI_ROOT: Path | None = None   # --tteutgi-root: 다른 판 뜯기 폴더(<root>/<id>/뜯기.json)를 먼저 본다


def tteutgi(slug: str, vid: str) -> Path:
    if TTEUTGI_ROOT and (TTEUTGI_ROOT / vid / "뜯기.json").exists():
        return TTEUTGI_ROOT / vid / "뜯기.json"
    p = ROOT / "channel" / slug / "뜯기" / vid / "뜯기.json"
    return p if p.exists() else Path(f"C:/숏템_칼카피/{slug}/engine_뜯기/{vid}/뜯기.json")


def bench_caption(mp4: str, cache: Path) -> dict:
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    from tools.calcopy.engine import bench_one
    m = bench_one.measure(mp4, layout_mode="single")
    its = [i for i in (m.get("captions") or {}).get("items", []) if i.get("lines", 0) > 0]
    gl = (m.get("captions") or {}).get("glyph") or []
    vl = m.get("vl") or {}
    out = {"top_y": st.median(i["top_y"] for i in its) if its else None, "line_h": st.median(g["line_h"] for g in gl) if gl else None,
           "ink": (vl.get("caption") or {}).get("ink"), "outline": sum(bool(g.get("outline")) for g in gl) * 2 > len(gl) if gl else None,
           "outline_px": st.median(g["outline_px"] for g in gl if g.get("outline_px")) if any(g.get("outline_px") for g in gl) else None,
           "band": (vl.get("caption") or {}).get("band")}
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def temp_caption(frame: dict, bc: dict) -> dict:
    """bench 자막 측정 → 임시 자막 층(그 편 설명서에 넣는다)."""
    from tools.calcopy.engine.to_frame import size_and_top
    F = copy.deepcopy(frame)
    if not bc.get("top_y") or not bc.get("line_h"):
        return F
    fit = size_and_top(TEMP_CAP_FONT, None, bc["top_y"], bc["line_h"], None)
    cap = next((l for l in F["layers"] if l.get("role") == "caption"), None)
    layer = {"kind": "text", "role": "caption", "x": 540, "w": 1000, "align": "center", "y": fit["y"], "lines": 1,
             "font": TEMP_CAP_FONT, "size": fit["size"], "line_h": fit["line_h"],
             "rgb": [255, 255, 255] if bc.get("ink") == "bright" else [0, 0, 0], "line_rgb": None,
             "outline": {"px": int(bc.get("outline_px") or 3), "rgb": [0, 0, 0] if bc.get("ink") == "bright" else [255, 255, 255]} if bc.get("outline") else None,
             "shadow": None, "box": None, "italic": False, "letter_spacing": 0, "enter": None}
    if cap:
        F["layers"][F["layers"].index(cap)] = layer
    else:
        F["layers"].append(layer)
    F.setdefault("made_from", {}).setdefault("notes", []).append(
        f"자막 층 = 임시(bench 측정 첫 줄 y {bc['top_y']}·줄 높이 {bc['line_h']}·{bc.get('ink')}·외곽선 {bc.get('outline')}, 글꼴 모름 → {TEMP_CAP_FONT}) — 분석기 D9 수리 전")
    return F


FIXED: dict = {}   # 대조로 못 박은 값(manifest.fixed) — 다시 만들어도 이어 붙인다(예: [광고] 외곽선 3px)


def build(preset_dir: Path, slug: str, ids: list[str], frames: dict, note: str) -> dict:
    mp = preset_dir / "manifest.json"
    if mp.exists():
        FIXED.update(json.loads(mp.read_text(encoding="utf-8")).get("fixed") or {})
    shutil.rmtree(preset_dir, ignore_errors=True)
    M = None
    for vid in ids:
        J = json.loads(tteutgi(slug, vid).read_text(encoding="utf-8"))
        M = P.save(J, frames[vid], preset_dir, vid, str(tteutgi(slug, vid)).replace("\\", "/"),
                   caption_style=preset_dir.name, caption_note=note)
    for path, f in FIXED.items():
        M = P.fix_value(preset_dir, path, f["value"], f["why"])
    return M


def frame_rows(cmp_json: Path) -> list[dict]:
    R = json.loads(cmp_json.read_text(encoding="utf-8"))
    return [r for r in R["rows"] if r.get("layer", "pixel") == "pixel" and r["key"].split("#")[0] in FRAME_KEYS]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True); ap.add_argument("--style", required=True)
    ap.add_argument("--frames", required=True); ap.add_argument("--ids", nargs="+", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--no-loo", action="store_true")
    ap.add_argument("--note", default="워커 점검.md 분류")
    ap.add_argument("--tteutgi-root", help="뜯기 폴더(<root>/<id>/뜯기.json) — 분석기 새 판으로 다시 뜯은 것")
    ap.add_argument("--rejudge", help="렌더 없이 이 loo.json 을 두 층으로 다시 판정(결과 같은 폴더 loo_judge.json)")
    if argv is None and "--rejudge" in sys.argv:
        i = sys.argv.index("--rejudge"); lp = Path(sys.argv[i + 1])
        two = judge(json.loads(lp.read_text(encoding="utf-8")))
        (lp.parent / "loo_judge.json").write_text(json.dumps(two, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        for k, v in two.items():
            print(k, "두 층 판정", v["in"], "/", v["n"], "밖:", v["defects"])
        return
    a = ap.parse_args(argv)
    global TTEUTGI_ROOT
    TTEUTGI_ROOT = Path(a.tteutgi_root) if a.tteutgi_root else None
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    frames = {}
    for vid in a.ids:
        f = json.loads((Path(a.frames) / f"frame_{vid}.json").read_text(encoding="utf-8"))
        J = json.loads(tteutgi(a.slug, vid).read_text(encoding="utf-8"))
        cap = next((l for l in f["layers"] if l.get("role") == "caption"), None)
        if "창안" in a.style and cap is not None:
            frames[vid] = temp_caption(f, bench_caption(J["source"], out / f"bench_cap_{vid}.json"))
        else:
            frames[vid] = f
    M = build(ROOT / "channel" / a.slug / "preset" / a.style, a.slug, a.ids, frames, a.note)
    print("프리셋", a.style, "변수", M["variables"])
    if a.no_loo or len(a.ids) < 2:
        return
    results = {}
    for held in a.ids:
        rest = [x for x in a.ids if x != held]
        d = out / f"loo_{held}"
        pdir = d / a.slug / "preset" / "loo"
        Mh = build(pdir, a.slug, rest, frames, a.note)
        pre, Mh = P.load(pdir)
        title = next(l for l in frames[held]["layers"] if l.get("role") == "title")
        F = P.apply(pre, None, {"layers[text:title].text": title["text"]}, Mh["variable_stats"], None, Mh["rules"])
        fp = d / "frame.json"; fp.write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
        J = json.loads(tteutgi(a.slug, held).read_text(encoding="utf-8"))
        J["captions"] = {"spans": [], "items": []}           # 자막 글 비움(재료 창 안에 원본 자막이 박혀 있다)
        jp = d / "J.json"; jp.write_text(json.dumps(J, ensure_ascii=False), encoding="utf-8")
        run = lambda c: subprocess.run(c, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")  # noqa: E731
        r1 = run([sys.executable, "tools/calcopy/frame_video.py", str(fp), str(jp), str(d / "vid"), "--src-window"])
        if r1.returncode:
            results[held] = {"failed": r1.stderr[-800:]}; continue
        r2 = run([sys.executable, "tools/calcopy/engine/compare.py", J["source"], str(d / "vid" / "ours.mp4"), "--out", str(d / "cmp"), "--layout", "single"])
        if r2.returncode not in (0, 1):
            results[held] = {"failed": r2.stderr[-800:]}; continue
        rows = frame_rows(d / "cmp" / "차이표.json")
        results[held] = {"rows": [{k: r.get(k) for k in ("key", "name", "orig", "ours", "diff", "status")} for r in rows],
                         "in": sum(r["status"] == "in" for r in rows), "n": len(rows), "frame": str(fp),
                         "side_by_side": str(d / "cmp" / "side_by_side.jpg")}
        print(held, results[held]["in"], "/", results[held]["n"])
    (out / "loo.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    two = judge(results)
    (out / "loo_judge.json").write_text(json.dumps(two, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for k, v in two.items():
        print(k, "두 층 판정", v["in"], "/", v["n"], "밖:", v["defects"])


# ── LOO 판정 두 층(관제 2026-10-16) — 판정은 여기 한 곳 ─────────────────────────────────────────────
# 고정 항목(그 하위 스타일이면 편마다 같아야 하는 것) = 뺀 편과 compare 기준 그대로.
# 변수 항목(편집자가 편마다 고르는 값: 제목 크기·줄 높이·창 y·자간과 그 결과인 제목 띠 획·잉크) = 뺀 편의 값을 맞출 수 없는 게
#   정상이므로, 우리 값이 다른 편들의 원본 잰 값 [min×0.9, max×1.1] 안이면 '안'.
VAR_PAD = 0.10
TITLE_BAND_MIN = 1        # 띠 #0 = 창 위 맨 윗줄([광고] 문구, 고정) · #1 이상 = 제목 줄(변수)


def _kind(key: str) -> str:
    base, _, idx = key.partition("#")
    if base.startswith("band.") and idx and int(idx) >= TITLE_BAND_MIN:
        return "var"
    return "fixed"


def _in_range(v, others):
    lo, hi = min(others) * (1 - VAR_PAD), max(others) * (1 + VAR_PAD)
    return lo <= v <= hi, [round(lo, 4), round(hi, 4)]


def judge(results: dict) -> dict:
    """results(loo.json) → 편마다 두 층 판정 줄. 창 [x,y,w,h] 는 둘로 가른다: x·w·아래 끝(고정, ≤4px) / y(변수)."""
    ok = {k: v for k, v in results.items() if "rows" in v}
    orig = {k: {r["key"]: r["orig"] for r in v["rows"]} for k, v in ok.items()}
    out = {}
    for held, v in ok.items():
        others = [o for o in ok if o != held]
        rows = []
        for r in v["rows"]:
            key = r["key"]
            if key == "frame.window":
                (ox, oy, ow, oh), (ux, uy, uw, uh) = r["orig"], r["ours"]
                d = max(abs(ox - ux), abs(ow - uw), abs((oy + oh) - (uy + uh)))
                rows.append({"key": "frame.window.fixed", "name": "영상 창 x·w·아래 끝", "tier": "고정",
                             "orig": [ox, ow, oy + oh], "ours": [ux, uw, uy + uh], "diff": d, "in": d <= 4, "rule": "≤4px"})
                ys = [orig[o][key][1] for o in others if key in orig[o]]
                inn, rg = _in_range(uy, ys) if ys else (False, None)
                rows.append({"key": "frame.window.y", "name": "영상 창 y", "tier": "변수", "orig": oy, "ours": uy,
                             "range": rg, "others": ys, "in": inn, "rule": "다른 편 범위 ±10%"})
                continue
            if _kind(key) == "var":
                vals = [orig[o][key] for o in others if key in orig[o] and isinstance(orig[o][key], (int, float))]
                inn, rg = _in_range(r["ours"], vals) if vals else (False, None)
                rows.append({"key": key, "name": r["name"], "tier": "변수", "orig": r["orig"], "ours": r["ours"],
                             "range": rg, "others": vals, "in": inn, "rule": "다른 편 범위 ±10%"})
            else:
                rows.append({"key": key, "name": r["name"], "tier": "고정", "orig": r["orig"], "ours": r["ours"],
                             "diff": r.get("diff"), "in": r["status"] == "in", "rule": "compare 기준"})
        out[held] = {"rows": rows, "in": sum(x["in"] for x in rows), "n": len(rows),
                     "defects": [x["name"] for x in rows if not x["in"]]}
    return out


if __name__ == "__main__":
    main()
