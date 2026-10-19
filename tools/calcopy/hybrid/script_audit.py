"""하이브리드 대본 점검 — **판 설정의 대본 규칙**(styles/<판>.json script.audit + _common forbid)으로 잰다 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/script_audit.py <대본.json> [<대본.json> …] [--version <판>]

판 = --version, 없으면 대본 경로의 폴더 이름(…/키치잇판/대본.json), 그것도 아니면 경로에 '재미썸홈' → 재미썸홈판, 그 밖 잇썸홈판.
규칙 종류(판 설정 script.audit):
  engine(잇썸홈 두유노 judge·points / 재미썸홈 이븐쇼핑 points — 판단 주인 engine/script_frame, 옛 동작 그대로)
  first_line · last_line · count · tts_chars · tts_total_chars · no_adjacent · ending(which=first_tts|last_tts|all_tts|rest_tts, min_share)
  has_line · forbid_in · cap_chars · orig_span · narr_share · est_length — 기준 숫자는 판 설정에만 있다(여기서 새로 정하지 않는다).
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
    for r in st["script"].get("audit") or []:
        if r["kind"] == "engine":
            e = engine(r["name"], d, lines)
            res["engine"] = e
            ok &= e["ok"]
            continue
        good, why = rule_check(r, d, st)
        res["rules"].append({"kind": r["kind"], "ok": good, "why": why, **({"rule": r["why"]} if r.get("why") else {})})
        ok &= good
    for f in st["script"].get("forbid") or []:
        bad = [l["id"] for l in d.get("lines") or [] if re.search(f["pattern"], (l.get("text") or l.get("tts") or "") + " " + " ".join(_caps(l)))]
        if bad:
            res["rules"].append({"kind": "forbid", "ok": False, "why": f"{f['why']} {bad}"}); ok = False
    res["narr"] = [SF.narr_rules(l["text"]) for l in lines]
    res["ok"] = bool(ok)
    return res


def main():
    args = sys.argv[1:]
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
