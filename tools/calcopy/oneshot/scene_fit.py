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
    material_auto.fit_judge(재료 고르기 때 판정, 7/4/1)와는 다른 자다 — 완성본 측정은 이것 하나."""
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


if __name__ == "__main__":
    for a in sys.argv[1:]:
        r = measure(Path(a))
        print("==", a, r["summary"])
        for x in r["rows"]:
            print(f"  {x['i']:2} {x.get('score')!s:>4} «{x['piece']}»  보임: {x.get('seen', x.get('why', ''))[:40]}  |  필요: {x.get('want', '')[:40]}")
