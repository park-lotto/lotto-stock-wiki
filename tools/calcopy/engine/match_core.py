# 재현일치도 비교 주인(관제 337 모둠경제 롱폼, Jev F4 근본해결 0.79·두더지 0.16).
# 벤치 측정값 묶음 ↔ 우리 측정값 한 벌을 칸 규칙(key, kind, tol, core, why)으로 비교한다. 측정은 하지 않는다(측정 주인 = 각 라인의 measure).
# kind 의 뜻은 쇼츠 tools/calcopy/engine/kal_analyze.match_table(543줄~)을 따른다. 원본과 **다른 점**(일부러 · 감시 지적 11-07):
#  ① range: 원본은 len.duration 의 brange(벤치 min~max)를 rel 판정에만 쓰고 range 칸엔 brange 가 있을 때만 — 여기선 rel·rel0·rel_slow·pctp·range
#     모든 칸에 벤치 편별 min~max(span)를 넘긴다(편 수 SPAN_MIN 이상일 때 · len.duration 은 1편부터 — RANGE_ALWAYS).
#     원본도 rel·rel0·rel_slow·pctp 는 _bench_span 으로 같은 넓히기를 한다. range 는 span 이 없으면 out(원본은 brange 없으면 out — 같음).
#  ② rel_slow: 원본은 b=0 이면 0 나누기로 죽는다 → 여기선 failed('벤치 0').
#  ③ rel0 발 수 규칙(원본 n_ok: key 가 '.rate' 로 끝나고 |(o−b)×우리 길이| ≤ 0.5발이면 in): judge_cell 의 count_dur 인자로 넣었다 — match 가
#     rel0·'.rate' 칸에 우리 len.duration 을 넘긴다(원본과 같은 조건).
#  ④ 원본의 쇼츠 전용 특수 in 3종은 **뺐다**: '.원음/.나레 둘 다 0줄 = 해당 없음' · fx.pos 꾸밈 0 해당 없음 · cut.median 둘 다 한 샷.
#     하이브리드 판 목표값 비교(HYBRID_OWN_KEYS)·len.duration 판 범위(own_len)도 없다. 롱폼에 필요해지면 칸 규칙으로 따로 넣는다.
#  ⑤ 원본 judge 'skip'(비교 안 함) 없음 — in/out/failed 셋뿐.
# TODO(나중 일): 쇼츠 match_table 의 칸별 판정도 이 judge_cell 로 옮긴다(지금은 쇼츠 라인을 건드리지 않는다 — 판정이 두 벌인 상태).
from __future__ import annotations

import os
from statistics import median

SPAN_MIN = 3        # 벤치 편별 범위(min~max)로 넓히려면 벤치가 이만큼 있어야 한다(kal_analyze.SPAN_MIN 과 같은 값)
RANGE_ALWAYS = ("len.duration",)   # 길이는 벤치 편 수와 상관없이 벤치 min~max 안이면 같다(쇼츠 match_table len.duration brange 와 같은 뜻)
KINDS = ("rel", "rel0", "rel_slow", "db", "pctp", "eq", "range")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _missing(x) -> bool:
    return x is None or (isinstance(x, str) and x.strip() in ("", "미측정"))


def _in_span(o, span) -> bool:
    return bool(span) and _num(o) and span[0] - 1e-9 <= o <= span[1] + 1e-9


def judge_cell(kind: str, tol: float, bench, ours, span=None, count_dur=None):
    """(판단 주인) 칸 하나 판정 → (judge, diff). judge ∈ in/out/failed — 못 잰 값(None·'미측정')은 failed(통과 아님).
    span = 벤치 편별 범위 (lo, hi) · pctp 분포 칸이면 {칸: (lo, hi)}.
    rel: |차%| ≤ tol 또는 span 안 · rel0: 벤치 0 이면 우리도 0 · rel_slow: 빠른 쪽(음수)은 tol 의 절반만, 느린 쪽은 tol 또는 span 위끝까지
    count_dur(rel0 만): 우리 길이(초) — |(o−b)×count_dur| ≤ 0.5(가장 가까운 정수 발 수)면 in(원본 n_ok)
    db: |차| ≤ tol(절대 차 — LUFS·개수) · pctp: 비율 차 %p ≤ tol(분포면 칸마다, 한쪽에만 있는 칸은 0) · eq: 같음 · range: span 안."""
    if kind not in KINDS:
        raise ValueError(f"모르는 kind: {kind}")
    if _missing(bench) or _missing(ours):
        return "failed", "미측정"
    b, o = bench, ours
    if kind == "eq":
        return ("in", "") if o == b else ("out", "다름")
    if kind == "pctp":
        if isinstance(b, dict) or isinstance(o, dict):
            if not (isinstance(b, dict) and isinstance(o, dict)):
                return "failed", "분포와 값이 섞임"
            diff = {k: round((o.get(k, 0.0) - b.get(k, 0.0)) * 100, 1) for k in sorted(set(b) | set(o))}
            sp = span if isinstance(span, dict) else {}
            ok = all(abs(v) <= tol or (k in sp and sp[k][0] - 1e-9 <= o.get(k, 0.0) <= sp[k][1] + 1e-9) for k, v in diff.items())
            return ("in" if ok else "out"), diff
        if not (_num(b) and _num(o)):
            return "failed", "숫자 아님"
        diff = round((o - b) * 100, 1)
        return ("in" if abs(diff) <= tol or _in_span(o, span) else "out"), diff
    if kind == "range":
        if not _num(o):
            return "failed", "숫자 아님"
        if not span:
            return "out", "벤치 범위 없음"
        return ("in" if _in_span(o, span) else "out"), f"벤치 {span[0]}~{span[1]}"
    if not (_num(b) and _num(o)):
        return "failed", "숫자 아님"
    if kind == "db":
        diff = round(o - b, 2)
        return ("in" if abs(diff) <= tol else "out"), diff
    if kind == "rel":
        diff = round((o - b) / b * 100, 1) if b else None
        return ("in" if (diff is not None and abs(diff) <= tol) or _in_span(o, span) else "out"), diff
    if kind == "rel0":
        diff = round((o - b) / b * 100, 1) if b else (0.0 if not o else "벤치 0")
        n_ok = bool(b and count_dur and abs((o - b) * count_dur) <= 0.5)
        return ("in" if (b and abs(diff) <= tol) or (not b and not o) or n_ok or _in_span(o, span) else "out"), diff
    # rel_slow
    if not b:
        return "failed", "벤치 0"
    diff = round((o - b) / b * 100, 1)
    return ("in" if -tol * 0.5 <= diff <= tol or (span and b <= o <= span[1] + 1e-9) else "out"), diff


def _bench_value(kind: str, vals: list):
    """벤치 편별 값 → 대표값. 숫자 = 중앙값 · eq = 가장 많은 값 · 분포(dict) = 칸별 중앙값(없는 칸 0)."""
    vals = [v for v in vals if not _missing(v)]
    if not vals:
        return None
    if all(isinstance(v, dict) for v in vals):
        ks = sorted({k for v in vals for k in v})
        return {k: round(median([v.get(k, 0.0) for v in vals]), 4) for k in ks}
    if all(_num(v) for v in vals) and kind != "eq":
        return round(median(vals), 4)
    from collections import Counter
    return Counter(map(str, vals)).most_common(1)[0][0] if kind == "eq" else None


def _span(key: str, kind: str, vals: list):
    vals = [v for v in vals if not _missing(v)]
    need = 1 if key in RANGE_ALWAYS else SPAN_MIN
    if len(vals) < need:
        return None
    if all(isinstance(v, dict) for v in vals):
        ks = sorted({k for v in vals for k in v})
        return {k: (min(v.get(k, 0.0) for v in vals), max(v.get(k, 0.0) for v in vals)) for k in ks}
    if all(_num(v) for v in vals):
        return (min(vals), max(vals))
    return None


def _bench_id(s: dict) -> str:
    return str(s.get("id") or os.path.splitext(os.path.basename(str(s.get("src") or "")))[0])


def match(rules, bench_stats: list[dict], ours_stats: dict, same_look_bench: str | None = None) -> dict:
    """(판단 주인) rules = [(key, kind, tol, core, why[, opt])] · bench_stats = 벤치 편마다 measure() 결과 · ours_stats = 우리 measure().
    opt(칸 규칙 꼬리 dict — 합격선 정의는 규칙 표 한 곳, 판정은 judge_cell):
      {"span_pad": 0.05} = 벤치 전체 편 min~max 를 위아래 5% 넓힌 범위(range 판정 · 편 수 1편부터)
      {"same_look": True} = same_look_bench(같은 틀 벤치 id) 한 편 값과 비교 · 나머지 편은 '<key>(다른 틀)' 참고 행. 지정 없으면 failed
    → {"rows": [{key, bench, ours, diff, judge, core, why, bench_span?}], "pass": 기준 칸 전부 in, "core_fail": [in 아닌 기준 칸]}"""
    rows = []
    for rule in rules:
        key, kind, tol, core, why = rule[:5]
        opt = rule[5] if len(rule) > 5 else {}
        o = ours_stats.get(key)
        if opt.get("same_look"):
            same = [s for s in bench_stats if same_look_bench and _bench_id(s) == same_look_bench]
            other = [s for s in bench_stats if not (same_look_bench and _bench_id(s) == same_look_bench)]
            b = same[0].get(key) if same else None
            judge, diff = judge_cell(kind, tol, b, o) if same else ("failed", "같은 틀 벤치 미지정" if not same_look_bench else f"벤치에 {same_look_bench} 없음")
            rows.append({"key": key, "bench": b, "ours": o, "diff": diff, "judge": judge, "core": bool(core), "n_bench": len(same),
                         "why": why + f" — 같은 틀 벤치 {same_look_bench or '?'}"})
            ov = [s.get(key) for s in other]
            ob = _bench_value(kind, ov)
            j2, d2 = judge_cell(kind, tol, ob, o)
            rows.append({"key": key + "(다른 틀)", "bench": ob, "ours": o, "diff": d2, "judge": j2, "core": False,
                         "n_bench": sum(not _missing(v) for v in ov), "why": "다른 틀 벤치 중앙과 비교 — 참고"})
            continue
        vals = [s.get(key) for s in bench_stats]
        b = _bench_value(kind, vals)
        if "span_pad" in opt:
            sp = _span("len.duration", kind, vals)        # 1편부터 min~max(RANGE_ALWAYS 와 같은 규칙)
            pad = float(opt["span_pad"])
            sp = (sp[0] * (1 - pad), sp[1] * (1 + pad)) if isinstance(sp, tuple) else sp
            sp = (round(sp[0], 4), round(sp[1], 4)) if isinstance(sp, tuple) else sp
        else:
            sp = _span(key, kind, vals) if kind in ("rel", "rel0", "rel_slow", "pctp", "range") else None
        cd = ours_stats.get("len.duration") if kind == "rel0" and key.endswith(".rate") else None
        judge, diff = judge_cell(kind, tol, b, o, sp, count_dur=cd if isinstance(cd, (int, float)) else None)
        rows.append({"key": key, "bench": b, "ours": o, "diff": diff, "judge": judge, "core": bool(core), "why": why,
                     "n_bench": sum(not _missing(v) for v in vals), **({"bench_span": sp} if sp else {})})
    core_fail = [r["key"] for r in rows if r["core"] and r["judge"] != "in"]
    return {"rows": rows, "pass": bool(any(r["core"] for r in rows)) and not core_fail, "core_fail": core_fail}


def match_md(T: dict, title: str = "") -> str:
    mark = {"in": "✓", "out": "✗", "failed": "미측정"}
    L = [f"# 재현일치도 {title} — **{'통과' if T['pass'] else '미달'}**", "",
         "| 항목 | 벤치(편 수) | 우리 | 차 | 판정 | 기준 | 자·합격선 |", "|---|---|---|---|---|---|---|"]
    for r in T["rows"]:
        L.append(f"| {r['key']} | {r['bench']} ({r['n_bench']}) | {r['ours']} | {r['diff']} | {mark.get(r['judge'], r['judge'])} | "
                 f"{'기준' if r['core'] else '참고'} | {r['why']} |")
    L += ["", f"미달 기준 칸: {', '.join(T['core_fail']) or '없음'} · 판정 = 기준 칸 전부 ✓ 일 때만 통과(미측정은 통과가 아니다)."]
    return "\n".join(L) + "\n"
