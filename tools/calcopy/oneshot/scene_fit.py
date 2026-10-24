# -*- coding: utf-8 -*-
"""원샷링크딸깍 — 완성본의 대사↔장면 맞음 측정(사장님 10-18 "대사에 맞는 편집포인트의 영상매칭이 안됐다").

    PYTHONUTF8=1 py tools/calcopy/oneshot/scene_fit.py <make 폴더> [<make 폴더> …]

make 폴더의 timeline.json(자막 조각 t0~t1) + final.mp4 → 조각마다 가운데 프레임 → material_auto.fit_judge(= judge_rubric 껍데기)로 0~10점.
결과 = make/scene_fit.json + 화면 요약. 판정은 여기서 새로 하지 않는다.
"""
from __future__ import annotations

import json
import re
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


MAX_ITEMS = 30     # 컷이 더 많으면 고르게 30개(편당 시트 3장)
PER_SHEET = 10     # 시트 한 장 = 컷 10칸(컷마다 처음·가운데·끝 3프레임 띠)
RUBRIC_V = "rubric:v1(2026-10-25)"
SKIP_ROLES = ("훅", "이음", "다리")     # 이 역할 줄의 컷은 '7 미만 비율' 분모에서 뺀다(표준 §11 ④ⓓ — 연결 줄 4~5점은 정상, 지침서 §3-4)
RUBRIC = """완성 쇼츠의 컷마다 '자막(대사)이 말하는 것이 화면에 보이나'를 채점한다. 칸마다 같은 컷의 처음·가운데·끝 3프레임이 가로로 붙어 있다(번호 = 노란 숫자).
기준점(이 다섯 점 중 하나만 준다):
10 = 대사가 말하는 동작·상태·대상이 다 보인다
7 = 대상과 그 상태는 보인다(동작 순간은 아니어도)
5 = 대상(제품·사람)만 보인다 — 대사가 말하는 상태·동작은 안 보인다
3 = 관련 소품·배경만 보인다
1 = 대사와 무관하다(다른 물건·다른 장면)
짧은 자막 조각은 '문장' 전체의 뜻으로 판단한다. 감탄·반응 대사("세상에!")는 그 반응(표정·몸짓)이 보이면 10.
[대사] (번호: «자막 조각» / 문장: 그 줄 전체)
{rows}
출력 JSON만: {{"fits":[{{"n":번호,"score":10|7|5|3|1,"seen":"화면에 보이는 것 한국어 한 줄"}}]}}"""


def _frame(mp4: Path, t: float, h: int = 400):
    import io
    from PIL import Image
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale=-2:{h}",
                        "-f", "image2pipe", "-vcodec", "png", "-"], stdin=subprocess.DEVNULL, capture_output=True).stdout
    return Image.open(io.BytesIO(b)).convert("RGB") if b else Image.new("RGB", (round(h * 9 / 16), h), (60, 0, 0))


def render_items(work: Path, out_dir: Path, roles: dict | None = None) -> list[dict]:
    """공용 렌더러(render_bench) 산출 → 컷마다 {img(처음·가운데·끝 3프레임 띠), piece(그 순간 자막), line(그 줄 전체), role, cut}.
    입력 = work/render/timeline.json(cuts) · 자막표.json(rows) · final.mp4 · roles = {줄 id: 대본 role}. 그림만 뽑는다(판정 안 함)."""
    from PIL import Image
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
        a, b = float(c["t0"]), float(c["t1"])
        mid = (a + b) / 2
        ts = [a + min(0.1, (b - a) / 4), mid, b - min(0.1, (b - a) / 4)]
        fr = [_frame(R / "final.mp4", t) for t in ts]
        strip = Image.new("RGB", (sum(f.width for f in fr) + 8, max(f.height for f in fr)), "white")
        x = 0
        for f in fr:
            strip.paste(f, (x, 0))
            x += f.width + 4
        img = out_dir / f"cut{k:02d}.jpg"
        strip.save(img, quality=85)
        here = [r.get("text") or "" for r in rows if float(r["t0"]) <= mid < float(r["t1"])]
        items.append({"img": str(img), "piece": " ".join(here) or "(자막 없음)", "line": " ".join(by_line.get(c.get("line"), [])),
                      "role": (roles or {}).get(c.get("line")),
                      "cut": {"line": c.get("line"), "src": c.get("src"), "ss": c.get("ss"), "t0": c["t0"], "t1": c["t1"], "see": c.get("see")}})
    return items


def _sheet(chunk: list[dict], dst: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    from tools.calcopy.engine.material_auto import FONT_B
    W, H, cols = 690, 410, 2
    sh = Image.new("RGB", (cols * (W + 6), ((len(chunk) + cols - 1) // cols) * (H + 6)), "white")
    d = ImageDraw.Draw(sh)
    font = ImageFont.truetype(FONT_B, 30)
    for j, it in enumerate(chunk):
        x, y = (j % cols) * (W + 6), (j // cols) * (H + 6)
        if it.get("img") and Path(it["img"]).exists():        # 그림 없는 칸은 빈칸(번호만) — 답은 '안 보임'으로 온다
            im = Image.open(it["img"]).convert("RGB")
            im.thumbnail((W, H))
            sh.paste(im, (x, y))
        d.rectangle([x, y, x + 52, y + 38], fill="black")
        d.text((x + 6, y + 2), str(j), font=font, fill="yellow")
    sh.save(dst, quality=88)
    return dst


def _ask(llm, sheet: Path, chunk: list[dict], tag: str) -> dict:
    from tools.calcopy.engine.material_auto import _as_int
    rows = "\n".join(f"{j}: «{it['piece']}» / 문장: {it['line']}" for j, it in enumerate(chunk))
    r, err = llm([sheet.read_bytes()], RUBRIC.format(rows=rows), tag)
    return {_as_int(x.get("n")): x for x in (r or {}).get("fits") or [] if isinstance(x, dict) and _as_int(x.get("score")) is not None}


def judge_rubric(items: list[dict], wd: Path, llm, cache: Path | None = None) -> list[dict]:
    """(판단 주인 — 완성본 대사↔장면 채점) 기준점 루브릭 RUBRIC · 시트 10칸 · 2회 채점 중앙값, 두 점수 차 ≥2 면 3회째(표준 §11 ④).
    같은 시트(그림·글 sha)는 cache 에서 다시 쓴다. 반환 = items 순서로 {score, scores, seen}.
    대사↔장면 판정은 이것 한 벌 — 완성본 측정(measure_render)·계획 매칭(hybrid/material_fit)·재료 고르기(material_auto.fit_judge 껍데기)가 다 부른다(지시서 14)."""
    import hashlib
    import statistics
    from tools.calcopy.engine.material_auto import _as_int
    fdir = Path(wd) / "fit"
    fdir.mkdir(parents=True, exist_ok=True)
    C = json.loads(cache.read_text(encoding="utf-8")) if cache and cache.exists() else {}
    out = []
    for c0 in range(0, len(items), PER_SHEET):
        chunk = items[c0:c0 + PER_SHEET]
        sp = _sheet(chunk, fdir / f"rubric_{c0 // PER_SHEET}.jpg")
        key = hashlib.sha256(sp.read_bytes() + json.dumps([(it["piece"], it["line"]) for it in chunk], ensure_ascii=False).encode()
                             + RUBRIC_V.encode()).hexdigest()[:24]
        runs = C.get(key)
        if not runs:
            runs = [_ask(llm, sp, chunk, "ma_fit:rubric") for _ in range(2)]

            def sc_of(r, j):
                return _as_int((r.get(j) or {}).get("score"))
            if any(sc_of(runs[0], j) is None or sc_of(runs[1], j) is None or abs(sc_of(runs[0], j) - sc_of(runs[1], j)) >= 2
                   for j in range(len(chunk))):
                runs.append(_ask(llm, sp, chunk, "ma_fit:rubric"))
            runs = [{str(k): v for k, v in r.items()} for r in runs]
            if cache and all(len(r) == len(chunk) for r in runs):
                C[key] = runs
                cache.write_text(json.dumps(C, ensure_ascii=False, indent=1), encoding="utf-8")
        for j in range(len(chunk)):
            sc = [_as_int((r.get(str(j)) or {}).get("score")) for r in runs]
            sc = [x for x in sc if x is not None]
            seen = next((str((r.get(str(j)) or {}).get("seen") or "") for r in runs if r.get(str(j))), "")
            out.append({"score": statistics.median(sc), "scores": sc, "seen": seen} if sc else {"score": None, "scores": [], "why": "답 없음"})
    return out


def summarize(scores: list, roles: list | None = None) -> dict:
    """점수 → 평균·FIT_MIN 미만 수·비율(판단 주인 = material_auto.FIT_MIN). roles 가 SKIP_ROLES 인 컷은 미만 비율 분모에서 뺀다."""
    from tools.calcopy.engine import material_auto as MA
    roles = roles or [None] * len(scores)
    sc = [s for s in scores if s is not None]
    base = [s for s, r in zip(scores, roles) if s is not None and not any(k in str(r or "") for k in SKIP_ROLES)]
    return {"n": len(scores), "judged": len(sc), "mean": round(sum(sc) / len(sc), 2) if sc else None,
            "below_min": sum(1 for s in base if s < MA.FIT_MIN), "below_base": len(base),
            "below_rate": round(sum(1 for s in base if s < MA.FIT_MIN) / len(base), 3) if base else None,
            "skipped_roles": len(sc) - len(base), "fit_min": MA.FIT_MIN}


def gold_check(scores: list, gold: list) -> dict:
    """손 정답 대조(표준 §11 ④ⓔ) — gold 칸마다 'low'(정답 ≤3) / 'high'(정답 ≥7) / None(판정 안 함).
    합격 = low 전부 <7 · high 전부 ≥6 (혼동 0)."""
    bad = [(k, g, s) for k, (g, s) in enumerate(zip(gold, scores))
           if (g == "low" and (s is None or s >= 7)) or (g == "high" and (s is None or s < 6))]
    return {"ok": not bad, "confused": bad, "n_low": gold.count("low"), "n_high": gold.count("high")}


def measure_render(work: Path, llm=None, out: Path | None = None, roles: dict | None = None) -> dict:
    """(render_bench 폴더 어댑터) 컷마다 대사↔장면 — judge_rubric(Claude 소넷). 결과 = out(기본 work/render/scene_fit.json)."""
    from tools.calcopy.engine import material_auto as MA
    work = Path(work)
    items = render_items(work, work / "render" / "fit", roles)
    llm = llm or MA.LLM()
    res = judge_rubric(items, work / "render", llm, cache=work / "render" / "scene_fit_cache.json")
    rows = [{"i": k, "piece": it["piece"], "role": it.get("role"), "cut": it["cut"], **r} for k, (it, r) in enumerate(zip(items, res))]
    o = {"made_by": "tools/calcopy/oneshot/scene_fit.measure_render", "rubric": RUBRIC_V,
         "summary": summarize([r.get("score") for r in rows], [r.get("role") for r in rows]), "rows": rows,
         "calls": len(getattr(llm, "calls", None) or [])}
    dst = Path(out) if out else work / "render" / "scene_fit.json"
    dst.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    return o


# ── 벤치 상위 편 재측정(같은 자 — 표준 §12-5 · 지시서 14) ─────────────────────────
BENCH_MIN_LINE = 0.25     # 이보다 짧은 줄(맨 앞 2프레임 썸네일 표지 등)은 컷이 아니라 뺀다
SENT_END = r"([?!.~？！]|요|다|죠|까|네)\s*$"      # 문장 끝(부호 또는 종결 어미)


def bench_items(doc: dict, mp4: Path, out_dir: Path) -> list[dict]:
    """벤치 완성본(남의 쇼츠) 줄판독 줄마다 {img(그 줄 시각 처음·가운데·끝 3프레임 띠 — 완성본 통째 화면), piece(줄 글), line(같은 화자 이어진 문장), role, eye(줄판독 눈 fit)}.
    우리 완성본 render_items 와 같은 꼴(통째 화면·3프레임·조각/문장) — 자가 같아야 비교가 된다."""
    from PIL import Image
    L = [l for l in doc.get("lines") or [] if (l.get("text") or "").strip() and float(l["t1"]) - float(l["t0"]) >= BENCH_MIN_LINE]
    sent, cur = [], []
    for k, l in enumerate(L):           # 문장 = 같은 화자가 이어 말한 줄(문장부호·화자 바뀜·0.5초 넘는 틈에서 끊음)
        if cur and (l.get("speaker") != cur[-1].get("speaker") or float(l["t0"]) - float(cur[-1]["t1"]) > 0.5):
            sent.append(cur); cur = []
        cur.append(l)
        if re.search(SENT_END, str(l.get("text"))):
            sent.append(cur); cur = []
    if cur:
        sent.append(cur)
    line_of = {id(l): " ".join(x["text"] for x in g) for g in sent for l in g}
    if len(L) > MAX_ITEMS:
        step = len(L) / MAX_ITEMS
        L = [L[int(k * step)] for k in range(MAX_ITEMS)]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for k, l in enumerate(L):
        a, b = float(l["t0"]), float(l["t1"])
        ts = [a + min(0.1, (b - a) / 4), (a + b) / 2, b - min(0.1, (b - a) / 4)]
        img = out_dir / f"line{k:02d}.jpg"
        if not img.exists():
            fr = [_frame(mp4, t) for t in ts]
            strip = Image.new("RGB", (sum(f.width for f in fr) + 8, max(f.height for f in fr)), "white")
            x = 0
            for f in fr:
                strip.paste(f, (x, 0))
                x += f.width + 4
            strip.save(img, quality=85)
        items.append({"img": str(img), "piece": l["text"], "line": line_of[id(l)], "role": l.get("role"),
                      "eye": l.get("fit") if isinstance(l.get("fit"), (int, float)) else None, "t": [a, b]})
    return items


def _pearson(xs: list, ys: list):
    pr = [(float(x), float(y)) for x, y in zip(xs, ys) if isinstance(x, (int, float)) and isinstance(y, (int, float))]
    if len(pr) < 3:
        return None
    mx, my = sum(x for x, _ in pr) / len(pr), sum(y for _, y in pr) / len(pr)
    sx = sum((x - mx) ** 2 for x, _ in pr) ** 0.5
    sy = sum((y - my) ** 2 for _, y in pr) ** 0.5
    return round(sum((x - mx) * (y - my) for x, y in pr) / (sx * sy), 3) if sx and sy else None


def bench_measure(slug: str, line_reads=None, src_dir=None, llm=None, ids: list | None = None, log=print) -> dict:
    """벤치 편마다 줄판독 줄 × 그 줄 시각의 완성본 3프레임 → judge_rubric(우리 완성본과 같은 함수) → channel/<slug>/_kal/상위편_목표.json.
    상위 편 = upgrade_table.Ctx.top()(조회 상위 50% — 판단 주인 그대로). 목표 = 상위 편 평균 p75 · 7 미만 비율 p25(표준 §12-2).
    파일에 다른 칸(15 의 밀도·cps)이 있으면 그대로 두고 scene_fit·ids·views 만 고친다."""
    import numpy as np
    from tools.calcopy.engine import material_auto as MA
    from tools.calcopy.engine import upgrade_table as UT
    line_reads = Path(line_reads) if line_reads else ROOT / "channel" / slug / "줄판독"
    src_dir = Path(src_dir) if src_dir else UT.DATA / slug / "src"
    st = {"bench": {"channel": slug, "line_reads": str(line_reads), "src_dir": str(src_dir)}}
    C = UT.Ctx(st, src_dir, src_dir)
    views, top = C.views(), C.top_ids()
    docs = [d for d in C.bench if d.get("id") and (not ids or d["id"] in ids)]
    llm = llm or MA.LLM()
    cache = src_dir / "_scene_fit_bench_cache.json"
    per, pairs = {}, []
    for d in docs:
        mp4 = src_dir / f"{d['id']}.mp4"
        if not mp4.exists():
            per[d["id"]] = {"error": f"완성본 없음 {mp4}"}
            log(f"[bench] {d['id']} 완성본 없음 — 미측정")
            continue
        wd = src_dir / "_scene_fit_bench" / d["id"]
        items = bench_items(d, mp4, wd / "strips")
        res = judge_rubric(items, wd, llm, cache=cache)
        sc = [r.get("score") for r in res]
        sm = summarize(sc, [it.get("role") for it in items])
        eye = [it.get("eye") for it in items]
        pairs += list(zip(sc, eye))
        ev = [e for e in eye if e is not None]
        per[d["id"]] = {**{k: sm[k] for k in ("n", "judged", "mean", "below_min", "below_base", "below_rate")},
                        "eye_mean": round(sum(ev) / len(ev), 2) if ev else None, "views": views.get(d["id"]), "top": d["id"] in top,
                        "rows": [{"t": it["t"], "piece": it["piece"], "role": it.get("role"), "eye": it.get("eye"), **r} for it, r in zip(items, res)]}
        log(f"[bench] {d['id']} 평균 {sm['mean']} · 7 미만 {sm['below_min']}/{sm['below_base']}({sm['below_rate']}) · 눈 {per[d['id']]['eye_mean']}")
    tops = [per[i] for i in top if i in per and per[i].get("mean") is not None]
    q = (lambda xs, p: round(float(np.percentile(xs, p)), 3) if xs else None)
    ms, bs = [x["mean"] for x in tops], [x["below_rate"] for x in tops if x.get("below_rate") is not None]
    sf = {"rubric": RUBRIC_V, "made_by": "tools/calcopy/oneshot/scene_fit.bench_measure", "group": "상위 편(조회 상위 50% — upgrade_table.Ctx.top)",
          "top_ids": top, "p75_mean": q(ms, 75), "p25_below7": q(bs, 25), "median_mean": q(ms, 50), "median_below7": q(bs, 50),
          "max_mean": max(ms) if ms else None, "corr_eye": _pearson([a for a, _ in pairs], [b for _, b in pairs]), "corr_n": sum(1 for a, b in pairs if a is not None and b is not None),
          "per_ep": per, "calls": len(getattr(llm, "calls", None) or [])}
    dst = ROOT / "channel" / slug / "_kal" / "상위편_목표.json"
    old = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
    out = {**old, "scene_fit": sf, "ids": [d["id"] for d in docs], "views": {d["id"]: views.get(d["id"]) for d in docs},
           "_note": old.get("_note") or "벤치 상위 편 같은 자 재측정(표준 §12-5) — scene_fit 은 지시서 14(scene_fit.bench_measure), 밀도·cps 칸은 15 가 더한다"}
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[bench] 상위 편 {top} → 평균 p75 {sf['p75_mean']} · 7 미만 p25 {sf['p25_below7']} · 눈 상관 {sf['corr_eye']}(n={sf['corr_n']}) → {dst}")
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["bench"]:          # PYTHONUTF8=1 py tools/calcopy/oneshot/scene_fit.py bench <slug> [--ids a,b]
        a = sys.argv[2:]
        ids = a[a.index("--ids") + 1].split(",") if "--ids" in a else None
        r = bench_measure(a[0], ids=ids)["scene_fit"]
        for i, v in r["per_ep"].items():
            print(f"  {i} 상위={v.get('top')} 조회={v.get('views')} 평균={v.get('mean')} 7미만={v.get('below_rate')} 눈={v.get('eye_mean')}")
        print("p75_mean", r["p75_mean"], "p25_below7", r["p25_below7"], "corr_eye", r["corr_eye"])
        sys.exit(0)
    for a in sys.argv[1:]:
        r = measure(Path(a))
        print("==", a, r["summary"])
        for x in r["rows"]:
            print(f"  {x['i']:2} {x.get('score')!s:>4} «{x['piece']}»  보임: {x.get('seen', x.get('why', ''))[:40]}  |  필요: {x.get('want', '')[:40]}")
