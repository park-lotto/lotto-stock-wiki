"""하이브리드 대본 점검 — **판 설정의 대본 규칙**(styles/<판>.json script.audit + _common forbid)으로 잰다 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/script_audit.py <대본.json> [<대본.json> …] [--version <판>]

판 = --version, 없으면 대본 경로의 폴더 이름(…/키치잇판/대본.json), 그것도 아니면 경로에 '재미썸홈' → 재미썸홈판, 그 밖 잇썸홈판.
규칙 종류(판 설정 script.audit):
  engine(잇썸홈 두유노 judge·points / 재미썸홈 이븐쇼핑 points — 판단 주인 engine/script_frame, 옛 동작 그대로)
  first_line · last_line · count · tts_chars · tts_total_chars · no_adjacent · ending(which=first_tts|last_tts|all_tts|rest_tts, min_share)
  has_line · forbid_in · cap_chars · orig_span · narr_share · est_length — 기준 숫자는 판 설정에만 있다(여기서 새로 정하지 않는다).
  tts_cps_spread(지시서 15, 표준 §12-4) — 나레 자막 조각(caps)의 예상 말속도 변동계수 ≤ max. 판에 규칙이 없어도 판 `targets.speech`
    (업그레이드 판, 07 주인)가 있으면 그 목표로 잰다(spread → 조각 수준 · cps_cv → 줄 수준). 걸리면 어느 줄을 어떻게 나눌지·몇 자 늘릴지 제안.

    PYTHONUTF8=1 py tools/calcopy/hybrid/script_audit.py fit-model "C:/숏템_칼카피/<slug>/*/render/자막표.json"   # 조각 시간 모형 다시 맞추기
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import script_frame as SF  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402
from tools.calcopy.hybrid.common import nchar  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FRAME = {"itssum": ROOT / "channel/homedesignnote/대본설명서/script_frame.json",
         "jaemi": ROOT / "channel/evenshopping/대본설명서/points.json"}


KIND = {"나레": "tts", "원음": "orig"}

# 나레 자막 조각 표시 초 예상 모형(판단 주인: tts_cps_spread 의 '예상 cps') — 조각 초 = base + per_char×글자 + punct×(조각 안 쉼표·마침표)
#   + first×(줄 첫 조각) + last×(줄 끝 조각). 근거 = 잇템로그 렌더 13편 나레 조각 214개 자막표(render/자막표.json t1−t0) 최소제곱, r² 0.689
#   (10-25 `script_audit.py fit-model "C:/숏템_칼카피/ititemlog/*/render/자막표.json"`). 글자만으로 보면(base 0.277 + 0.107×글자) r² 0.615 —
#   짧은 조각·줄 첫 조각이 느려 보이는 까닭(조각 뒤 쉼·줄 머리 쉼이 그 조각 표시 시간에 들어간다). per_char 0.119 ≈ 1/8.4 자/초(판 cps_target 8.6).
CHUNK_MODEL = {"base": 0.049, "per_char": 0.119, "punct": 0.305, "first": 0.192, "last": 0.047}
PUNCT_IN = r"[,，.!?…]"


def _narr_chunks(d: dict) -> list[dict]:
    """나레 줄의 자막 조각 [{line, j, text, n, punct, first, last}] — 조각 = 대본 caps(없으면 tts 통째 1조각)."""
    out = []
    for l in d.get("lines") or []:
        if l.get("kind") == "orig" or l.get("id") == "O":
            continue
        caps = _caps(l) or [(l.get("tts") or l.get("text") or "").strip()]
        caps = [c for c in caps if nchar(c)]
        for j, c in enumerate(caps):
            out.append({"line": l.get("id"), "j": j, "text": c, "n": nchar(c), "punct": _punct_in(c), "first": j == 0, "last": j == len(caps) - 1})
    return out


def _punct_in(t: str) -> int:
    return len(re.findall(PUNCT_IN, t.rstrip(" ?!.…,")))


def _chunk_sec(c: dict, M: dict) -> float:
    return M["base"] + M["per_char"] * c["n"] + M["punct"] * c["punct"] + M["first"] * c["first"] + M["last"] * c["last"]


def _cv(xs: list[float]) -> float | None:
    import statistics
    if len(xs) < 3:
        return None
    m = statistics.mean(xs)
    return round(statistics.pstdev(xs) / m, 4) if m else None


def _model(r: dict) -> dict:
    M = {**CHUNK_MODEL, **(r.get("model") or {})}
    if isinstance(r.get("cps"), (int, float)) and r["cps"] > 0 and "per_char" not in (r.get("model") or {}):
        M["per_char"] = 1.0 / float(r["cps"])
    return M


def _resplit(words: list[str], k: int):
    from itertools import combinations
    for cut in combinations(range(1, len(words)), k - 1):
        yield [" ".join(words[a:b]) for a, b in zip((0,) + cut, cut + (len(words),))]


def cps_spread(d: dict, r: dict, st: dict | None = None) -> dict:
    """(판단 주인: 대본 단계 말속도 편차) 조각·줄 예상 cps 와 변동계수 + 고칠 제안. level = chunk(조각, 기본) | line(줄).
    다시 나누기 제안의 조각 글자 범위 = [이 대본의 가장 짧은 조각, 판 cap_chars 규칙 max(없으면 이 대본의 가장 긴 조각)] — 없는 기준을 새로 정하지 않는다."""
    import statistics
    M = _model(r)
    ch = _narr_chunks(d)
    for c in ch:
        c["sec"] = _chunk_sec(c, M)
        c["cps"] = c["n"] / c["sec"]
    by_line: dict = {}
    for c in ch:
        by_line.setdefault(c["line"], []).append(c)
    lines = {k: sum(c["n"] for c in v) / sum(c["sec"] for c in v) for k, v in by_line.items()}
    level = r.get("level", "chunk")
    cv = _cv([c["cps"] for c in ch]) if level == "chunk" else _cv(list(lines.values()))
    sug = []
    caps_max = next((x["max"] for x in ((st or {}).get("script") or {}).get("audit") or [] if x.get("kind") == "cap_chars"), None)
    lo_n = min((c["n"] for c in ch), default=1)
    hi_n = caps_max or max((c["n"] for c in ch), default=99)
    if level == "chunk":
        # 줄마다 같은 조각 수로 낱말 경계에서 다시 나눠 본다(대사·TTS 글 그대로 — 자막 나누기만 바뀌어 다시 합성 안 함) → 편 전체 변동계수가 가장 낮은 나누기
        for lid, cs in by_line.items():
            words = " ".join(c["text"] for c in cs).split()
            if len(cs) < 2 or len(words) < len(cs):
                continue
            rest = [c["cps"] for c in ch if c["line"] != lid]
            best = None
            for parts in _resplit(words, len(cs)):
                if not all(lo_n <= nchar(t) <= hi_n for t in parts):
                    continue
                trial = [{"n": nchar(t), "punct": _punct_in(t), "first": k == 0, "last": k == len(parts) - 1} for k, t in enumerate(parts)]
                v = _cv(rest + [t["n"] / _chunk_sec(t, M) for t in trial])
                if v is not None and (best is None or v < best[0]):
                    best = (v, parts)
            cur = [c["text"] for c in cs]
            if best and best[1] != cur and cv is not None and best[0] < cv - 0.003:
                sug.append({"line": lid, "now": cur, "try": best[1], "chars": [nchar(t) for t in best[1]], "cv_if": best[0],
                            "why": f"자막 나누기만 바꿈(TTS 글 그대로) — 편 조각 변동계수 {cv} → {best[0]}"})
        sug.sort(key=lambda x: x["cv_if"])
    else:
        m = statistics.mean(lines.values()) if lines else 0
        for lid, v in sorted(lines.items(), key=lambda kv: -abs(kv[1] - m)):
            if m and abs(v / m - 1) > float(r.get("max") or 0.11):
                cs = by_line[lid]
                S, n = sum(c["sec"] for c in cs), sum(c["n"] for c in cs)
                k = (m * S - n) / (1 - m * M["per_char"]) if abs(1 - m * M["per_char"]) > 1e-6 else 0.0
                sug.append({"line": lid, "cps": round(v, 2), "mean": round(m, 2), "chars": n, "add_chars": round(k),
                            "why": f"예상 {v:.2f}자/초 vs 평균 {m:.2f} — 글자 {round(k):+d}자(조각 안 쉼표 하나 = {M['punct']:.2f}초)"})
    return {"level": level, "cv": cv, "max": r.get("max"), "lines": {k: round(v, 2) for k, v in lines.items()}, "suggest": sug[:5], "model": M,
            "chunks": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items()} for c in ch]}


def speech_rule(st: dict) -> dict | None:
    """판에 tts_cps_spread 규칙이 없을 때 판 targets.speech(업그레이드 판 목표, 07 주인)로 만드는 규칙 — spread(조각) 먼저, 없으면 cps_cv(줄)."""
    sp = (st.get("targets") or {}).get("speech") or {}
    for key, level in (("spread", "chunk"), ("cps_cv", "line")):
        g = (sp.get(key) or {}).get("ours_goal")
        if isinstance(g, (int, float)):
            return {"kind": "tts_cps_spread", "max": g, "level": level, "why": f"판 targets.speech.{key}.ours_goal(상위 편 p25 — {level} 수준)"}
    return None


def as_lines(d: dict) -> dict:
    """대본 꼴 맞추기(주인 한 곳): 최상위 lines(하이브리드 판들) 그대로 / 없고 final.lines(샥탬 shark 대본)면 그것을 lines 로 —
    샥탬 kind '나레/원음' 은 'tts/orig' 로. 최상위 lines 가 있으면 아무것도 안 바꾼다(옛 동작 그대로)."""
    if d.get("lines") or not (d.get("final") or {}).get("lines"):
        return d
    return {**d, "lines": [{**l, "kind": KIND.get(l.get("kind"), l.get("kind"))} for l in d["final"]["lines"]]}


def tts_lines(d: dict) -> list[dict]:
    out = []
    for l in d.get("lines") or []:
        if l.get("kind") == "orig" or l.get("id") == "O":
            continue
        t = l.get("tts") or l.get("text") or ""
        if t:
            out.append({**l, "text": l.get("text") or t})
    return out


def version_of(path: Path, given: str | None) -> str:
    if given:
        return given
    names = ST.names()
    for part in reversed(Path(path).parts):
        if part in names:
            return part
    return "재미썸홈판" if "재미썸홈" in str(path) else "잇썸홈판"


def engine(kind: str, d: dict, lines: list[dict]) -> dict:
    """옛 잇썸·재미썸 검사(동작 그대로)."""
    text = " ".join(l["text"] for l in lines)
    res = {}
    if kind == "itssum":
        frame = json.loads(FRAME["itssum"].read_text(encoding="utf-8"))
        j = SF.judge_like([l["text"] for l in lines], frame)
        res["judge"] = {"score": round(j["score"], 3), "pass": j["pass"], "hard_fail": j["hard_fail"],
                        "bad_parts": [k for k, v in j["parts"].items() if not v.get("ok")]}
        f = SF.features(text)
        res["endings"] = [SF.ending_of(s) for s in SF.sentences(text)]
        res["features"] = {k: f[k] for k in ("sent_len_mean", "connect_per_sent", "person1_ratio", "polite_ratio")}
        pc = SF.load_points(FRAME["itssum"])
    else:
        pc = json.loads(FRAME["jaemi"].read_text(encoding="utf-8"))
        res["polite"] = sum(1 for l in lines if l["text"].rstrip(" .,").endswith(("요", "니다")))
    pcr = SF.points_check(lines, pc)
    if pcr is not None:
        res["points"] = {"ok": pcr["ok"], "why": pcr["why"], "bad": pcr["bad"], "wow": [w for _, w in pcr["wow"]], "ing": pcr["ing"]}
    ok = (res.get("judge", {}).get("pass", True)) and (res.get("points", {}).get("ok", True))
    return {"ok": bool(ok), **res}


def _caps(l: dict) -> list[str]:
    if l.get("kind") == "orig":
        return [c[0] for c in l.get("caps_rel") or []] + [c["text"] if isinstance(c, dict) else c[1] if isinstance(c, list) else c for c in l.get("caps") or []]
    return [c["text"] if isinstance(c, dict) else c for c in l.get("caps") or []]


def _orig_sec(l: dict) -> float:
    sp = l.get("spans") or ([l["span"]] if l.get("span") else [])
    if l.get("pieces"):
        sp = [p["span"] for p in l["pieces"]]
    return sum(b - a for a, b in sp)


def rule_check(r: dict, d: dict, st: dict) -> tuple[bool, str]:
    L = d.get("lines") or []
    T = [l for l in L if l.get("kind") != "orig"]
    O = [l for l in L if l.get("kind") == "orig"]
    txt = lambda l: (l.get("text") or l.get("tts") or "").strip()
    k = r["kind"]
    if k == "first_line":
        got = L[0].get("kind", "tts") if L else None
        return got == r["is"], f"첫 줄 {got}"
    if k == "last_line":
        got = L[-1].get("kind", "tts") if L else None
        ok = got == r["is"] or (got == "tts" and r.get("or_tts_pattern") and re.search(r["or_tts_pattern"], txt(L[-1])))
        return bool(ok), f"끝 줄 {got}"
    if k == "count":
        n = len(T if r["of"] == "tts" else O)
        return r["min"] <= n <= r["max"], f"{r['of']} {n}줄 ({r['min']}~{r['max']})"
    if k == "tts_chars":
        bad = [(l["id"], nchar(txt(l))) for l in T if not (r["min"] <= nchar(txt(l)) <= r["max"])]
        return not bad, f"줄 글자 {r['min']}~{r['max']} 밖 {bad}"
    if k == "tts_total_chars":
        n = sum(nchar(txt(l)) for l in T)
        return r["min"] <= n <= r["max"], f"나레 전체 {n}자 ({r['min']}~{r['max']})"
    if k == "no_adjacent":
        bad = [(a["id"], b["id"]) for a, b in zip(L, L[1:]) if a.get("kind", "tts") == r["of"] and b.get("kind", "tts") == r["of"]]
        return not bad, f"{r['of']} 연달아 {bad}"
    if k == "ending":
        sel = {"first_tts": T[:1], "last_tts": T[-1:], "all_tts": T, "rest_tts": T[1:]}[r["which"]]
        hit = [bool(re.search(r["pattern"], txt(l))) for l in sel]
        share = sum(hit) / max(1, len(hit))
        need = r.get("min_share", 1.0)
        return share >= need, f"{r['which']} 어미 맞음 {sum(hit)}/{len(hit)} (≥{need}) 안 맞음 {[l['id'] for l, h in zip(sel, hit) if not h]}"
    if k == "has_line":
        n = sum(1 for l in (T if r["of"] == "tts" else L) if re.search(r["pattern"], txt(l)))
        return n >= r.get("min", 1), f"'{r.get('why', r['pattern'])}' {n}줄"
    if k == "forbid_in":
        bad = [l["id"] for l in (T if r["of"] == "tts" else L) if re.search(r["pattern"], txt(l))]
        return not bad, f"금지 '{r.get('why', r['pattern'])}' {bad}"
    if k == "cap_chars":
        bad = [(l["id"], c) for l in L for c in _caps(l) if nchar(c) > r["max"]]
        return not bad, f"자막 덩어리 {r['max']}자 넘음 {bad}"
    if k == "orig_span":
        if not O:
            return False, "원음 줄 없음"
        l = O[0] if r["which"] == "first" else O[-1]
        s = _orig_sec(l)
        return s <= r["max"], f"{r['which']} 원음 {s:.2f}초 (≤{r['max']})"
    if k == "tts_cps_spread":
        R = cps_spread(d, r, st)
        what = "조각" if R["level"] == "chunk" else "줄"
        if R["cv"] is None:
            return False, f"나레 {what}이 3개 미만 — 편차 못 잼"
        ok = R["cv"] <= r["max"]
        tip = "" if ok else " · 제안 " + " / ".join(
            (f"{s['line']} {s['now']} → {s['try']}(cv {s['cv_if']})" if "try" in s else f"{s['line']} {s['why']}") for s in R["suggest"][:3])
        return ok, f"{what} 예상 cps 변동계수 {R['cv']} (≤{r['max']}){tip}"
    if k in ("narr_share", "est_length"):
        cps = st.get("cps_target", 7.0)
        tn = sum(nchar(txt(l)) for l in T) / cps
        to = sum(_orig_sec(l) for l in O)
        gaps = 0.12 * max(0, len(L) - 1) + (st.get("timing") or {}).get("tail", 0.35)
        if k == "narr_share":
            sh = tn / max(0.01, tn + to)
            return r["min"] <= sh <= r["max"], f"나레 비중(어림) {sh:.2f} ({r['min']}~{r['max']})"
        tot = tn + to + gaps
        return r["min"] - 1 <= tot <= r["max"] + 1, f"어림 길이 {tot:.1f}초 ({r['min']}~{r['max']}, 렌더 뒤 다시 잰다)"
    return False, f"모르는 규칙 {k}"


def audit(path: Path, version: str | None = None) -> dict:
    d = as_lines(json.loads(Path(path).read_text(encoding="utf-8")))
    v = version_of(Path(path), version)
    st = ST.load(v)
    lines = tts_lines(d)
    res = {"file": str(path), "version": v, "n_lines": len(lines), "chars": sum(nchar(l["text"]) for l in lines), "rules": []}
    ok = True
    rules = list(st["script"].get("audit") or [])
    if not any(r.get("kind") == "tts_cps_spread" for r in rules) and speech_rule(st):
        rules.append(speech_rule(st))
    for r in rules:
        if r["kind"] == "engine":
            e = engine(r["name"], d, lines)
            res["engine"] = e
            ok &= e["ok"]
            continue
        good, why = rule_check(r, d, st)
        res["rules"].append({"kind": r["kind"], "ok": good, "why": why, **({"rule": r["why"]} if r.get("why") else {})})
        ok &= good
    for f in st["script"].get("forbid") or []:
        if f.get("of") == "tts":      # of: tts = 나레 줄만(원음 번역 자막은 방송 내용) · 샥탬 앞 칼카피(final.lines, hybrid 칸 없음)는 벤치 내용이라 대상 아님
            if (d.get("final") or {}).get("lines") and not d.get("hybrid"):
                continue
            sel = lines
        else:
            sel = d.get("lines") or []
        bad = [l.get("id", k) for k, l in enumerate(sel) if re.search(f["pattern"], (l.get("text") or l.get("tts") or "") + " " + " ".join(_caps(l)))]
        if bad:
            res["rules"].append({"kind": "forbid", "ok": False, "why": f"{f['why']} {bad}"}); ok = False
    res["narr"] = [SF.narr_rules(l["text"]) for l in lines]
    res["ok"] = bool(ok)
    return res


def fit_model(pattern: str) -> dict:
    """렌더 자막표(나레 조각 t1−t0)로 CHUNK_MODEL 을 다시 맞춘다 — 최소제곱. 결과를 보고 CHUNK_MODEL 을 근거 줄과 같이 손으로 고친다."""
    import glob
    import numpy as np
    X, Y, n_ep = [], [], 0
    for f in sorted(glob.glob(pattern)):
        rows = [r for r in json.loads(Path(f).read_text(encoding="utf-8")).get("rows") or []
                if (r.get("speaker") or r.get("kind")) == "narr" and float(r.get("t1") or 0) > float(r.get("t0") or 0)]
        n_ep += bool(rows)
        for i, r in enumerate(rows):
            t = r.get("text") or ""
            first = i == 0 or rows[i - 1].get("line") != r.get("line")
            last = i + 1 == len(rows) or rows[i + 1].get("line") != r.get("line")
            X.append([1, nchar(t), _punct_in(t), int(first), int(last)]); Y.append(float(r["t1"]) - float(r["t0"]))
    X, Y = np.array(X, float), np.array(Y, float)
    co, *_ = np.linalg.lstsq(X, Y, rcond=None)
    r2 = 1 - float(((Y - X @ co) ** 2).sum()) / float(((Y - Y.mean()) ** 2).sum())
    return {"episodes": n_ep, "chunks": len(Y), "r2": round(r2, 3), **dict(zip(("base", "per_char", "punct", "first", "last"), (round(float(c), 3) for c in co)))}


def main():
    args = sys.argv[1:]
    if args[:1] == ["fit-model"]:
        print(json.dumps(fit_model(args[1]), ensure_ascii=False))
        return 0
    ver = None
    if "--version" in args:
        i = args.index("--version"); ver = args[i + 1]; del args[i:i + 2]
    bad = 0
    for p in args:
        r = audit(Path(p), ver)
        bad += not r["ok"]
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
