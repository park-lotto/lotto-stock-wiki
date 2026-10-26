"""하이브리드 대본 점검 — **판 설정의 대본 규칙**(styles/<판>.json script.audit + _common forbid)으로 잰다 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/script_audit.py <대본.json> [<대본.json> …] [--version <판>]

판 = --version, 없으면 대본 경로의 폴더 이름(…/키치잇판/대본.json), 그것도 아니면 경로에 '재미썸홈' → 재미썸홈판, 그 밖 잇썸홈판.
규칙 종류(판 설정 script.audit):
  engine(잇썸홈 두유노 judge·points / 재미썸홈 이븐쇼핑 points — 판단 주인 engine/script_frame, 옛 동작 그대로)
  first_line · last_line · count · tts_chars · tts_total_chars · no_adjacent · ending(which=first_tts|last_tts|all_tts|rest_tts, min_share)
  has_line · forbid_in · cap_chars · orig_span · narr_share · est_length — 기준 숫자는 판 설정에만 있다(여기서 새로 정하지 않는다).
  tts_cps_spread(지시서 15, 표준 §12-4·§11-3 ⑲) — 나레 TTS 줄(문장) 예상 말속도 변동계수 ≤ max(줄 단위 — 자막 조각 나누기는 뼈대라 안 건드림).
    판에 규칙이 없어도 판 `targets.speech`(업그레이드 판, 07 주인)가 있으면 그 목표로 잰다. 걸리면 어느 줄을 몇 자 늘리거나 줄일지 제안.

    PYTHONUTF8=1 py tools/calcopy/hybrid/script_audit.py fit-model "C:/숏템_칼카피/<slug>/*/render/자막표.json"   # 줄 시간 모형 다시 맞추기
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

# 나레 TTS 줄(문장) 소리 초 예상 모형(판단 주인: tts_cps_spread 의 '예상 cps', 표준 §11-3 ⑲ — 말속도 편차는 **줄 단위** 자) —
#   줄 초 = base + per_char×글자 + punct×(줄 안 쉼표·마침표, 끝 부호 뺌). 근거 = 잇템로그 렌더 14편 나레 줄 99개(render/자막표.json 줄의 첫 조각 t0 ~ 끝 조각 t1)
#   최소제곱 r² 0.761(10-25 `script_audit.py fit-model "C:/숏템_칼카피/ititemlog/*/render/자막표.json"`). 자막 조각(caps) 나누기는 판 chunk_max_chars(뼈대) 몫 — 여기서 안 건드린다.
LINE_MODEL = {"base": 0.154, "per_char": 0.127, "punct": 0.412}
PUNCT_IN = r"[,，.!?…]"


def _punct_in(t: str) -> int:
    return len(re.findall(PUNCT_IN, t.rstrip(" ?!.…,")))


def _cv(xs: list[float]) -> float | None:
    import statistics
    if len(xs) < 3:
        return None
    m = statistics.mean(xs)
    return round(statistics.pstdev(xs) / m, 4) if m else None


def _model(r: dict) -> dict:
    return {**LINE_MODEL, **(r.get("model") or {})}


def cps_spread(d: dict, r: dict, st: dict | None = None) -> dict:
    """(판단 주인: 대본 단계 말속도 편차, 줄 단위) 나레 줄마다 예상 자/초 = 글자 ÷ 예상 초(LINE_MODEL) → 변동계수 + 고칠 제안
    (평균에서 먼 줄부터: 글자 몇 자 늘리기/줄이기 — 판 tts_chars 범위 안에서만, 줄 안 쉼표 빼기). 자막 나누기는 안 건드린다(⑲)."""
    import statistics
    M = _model(r)
    lines = {}
    for l in d.get("lines") or []:
        if l.get("kind") == "orig" or l.get("id") == "O":
            continue
        t = (l.get("tts") or l.get("text") or "").strip()
        n = nchar(t)
        if n:
            sec = M["base"] + M["per_char"] * n + M["punct"] * _punct_in(t)
            lines[l.get("id")] = {"chars": n, "punct": _punct_in(t), "sec": round(sec, 3), "cps": round(n / sec, 3)}
    cv = _cv([v["cps"] for v in lines.values()])
    rng = next((x for x in ((st or {}).get("script") or {}).get("audit") or [] if x.get("kind") == "tts_chars"), None)
    sug = []
    if cv is not None and cv > float(r.get("max") or 0):
        m = statistics.mean(v["cps"] for v in lines.values())
        for lid, v in sorted(lines.items(), key=lambda kv: -abs(kv[1]["cps"] - m)):
            S = M["base"] + M["punct"] * v["punct"]           # 글자에 안 붙는 초
            k = round((m * S) / (1 - m * M["per_char"]) - v["chars"]) if abs(1 - m * M["per_char"]) > 1e-6 else 0
            if rng:
                k = max(rng["min"] - v["chars"], min(rng["max"] - v["chars"], k))
            tip = f"글자 {k:+d}자" if k else "글자 그대로(범위 끝)"
            if v["punct"] and v["cps"] < m:
                tip += f" 또는 줄 안 쉼표 {v['punct']}개 빼기(하나 = {M['punct']:.2f}초)"
            sug.append({"line": lid, "cps": v["cps"], "mean": round(m, 2), "chars": v["chars"], "add_chars": k,
                        "why": f"예상 {v['cps']:.2f}자/초 vs 평균 {m:.2f} — {tip}"})
    return {"level": "line", "cv": cv, "max": r.get("max"), "lines": lines, "suggest": sug[:5], "model": M}


def speech_rule(st: dict) -> dict | None:
    """판에 tts_cps_spread 규칙이 없을 때 판 targets.speech(업그레이드 판 목표, 07 주인)로 만드는 규칙 — 줄 단위(⑲) = `cps_cv`(나레 문장 자).
    `spread`(자막 조각 표시 자)는 다른 자라 쓰지 않는다(§11-3 ⑲ 자를 섞지 않는다)."""
    sp = (st.get("targets") or {}).get("speech") or {}
    for key in ("cps_cv",):
        g = (sp.get(key) or {}).get("ours_goal")
        if isinstance(g, (int, float)):
            return {"kind": "tts_cps_spread", "max": g, "why": f"판 targets.speech.{key}.ours_goal(상위 편 p25 — TTS 줄 단위)"}
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


def version_of(path: Path, given: str | None, doc: dict | None = None) -> str:
    """판 정하기: --version → 경로 안 판 폴더 이름 → 대본의 채널 이름 + '판'(재미썸홈 → 재미썸홈판) → 경로에 '재미썸홈' → 잇썸홈판.
    대본 채널 칸(10-26): preset_make 작품(channel/evenshopping/작품N/대본.json '채널: 재미썸홈')이 옛 규칙으론 잇썸홈판으로 재지던 것을 바로잡는다."""
    if given:
        return given
    names = ST.names()
    for part in reversed(Path(path).parts):
        if part in names:
            return part
    if doc is None:
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
    ch = str((doc or {}).get("채널") or (doc or {}).get("channel") or "").strip() if isinstance(doc, dict) else ""
    if ch and f"{ch}판" in names:
        return f"{ch}판"
    return "재미썸홈판" if "재미썸홈" in str(path) else "잇썸홈판"


def engine_pc(kind: str, off: tuple = ()) -> dict | None:
    """engine 검사의 포인트 기준(pc) 주인 한 곳 — 검사(engine)와 대본 질문지(points_rule_for → flow._script_ask)가 같은 기준을 쓴다.
    10-27 실사고: 검사는 줄의 point·answer_at·facts 를 보는데 질문지엔 그 칸이 없어 7번 반려(통과 불가능)."""
    pc = SF.load_points(FRAME["itssum"]) if kind == "itssum" else json.loads(FRAME["jaemi"].read_text(encoding="utf-8"))
    if pc and "wow" in off:
        pc = {**pc, "wow": {**(pc.get("wow") or {}), "count": 0, "strong_min": 0}}
    return pc


def points_rule_for(version: str) -> str:
    """이 판 대본 검사(engine)가 요구하는 표시 칸 지시문 — 없으면 ''. 지시 글 주인 = script_frame.points_rule."""
    for r in (ST.load(version).get("script") or {}).get("audit") or []:
        if r.get("kind") == "engine":
            rule = SF.points_rule(engine_pc(r["name"], tuple(r.get("off") or ())))
            return (rule + "\n[표시 칸 — 검사가 글이 아니라 이 칸을 본다] 대본 lines 각 줄에 point(\"잉\"·\"와우\"·\"권위\" 등)·answer_at(잉 줄의 답이 나오는 뒤 줄 번호, 0부터)·"
                    "facts(그 줄 사실의 근거 = 조사.md 사실 번호 목록, 예 [\"f3\"]) 칸을 단다. 숫자·권위 줄과 와우 줄은 facts 가 비면 없는 것으로 친다.") if rule else ""
    return ""


def engine(kind: str, d: dict, lines: list[dict], off: tuple = ()) -> dict:
    """옛 잇썸·재미썸 검사(동작 그대로). off = 판 audit 칸 engine.off — 이 판에서 끄는 points 항목(지금은 'wow' 하나:
    와우 = 줄 머리 강한 연결어 3줄, 10-26 두유노판 — 벤치 상위 10편 연결어 줄 0%라 벤치를 따라 끔. 다른 판은 그대로)."""
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
    else:
        res["polite"] = sum(1 for l in lines if l["text"].rstrip(" .,").endswith(("요", "니다")))
    pc = engine_pc(kind, off)
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
    if k == "cap_chars":     # max "chunk_max_chars" = 판 caption.chunk_max_chars 를 그대로(조각 자수 판단은 그 칸 하나)
        mx = (st.get("caption") or {}).get("chunk_max_chars") if r["max"] == "chunk_max_chars" else r["max"]
        sel = [l for l in L if (l.get("kind") == "orig") == (r.get("of") == "orig")] if r.get("of") in ("tts", "orig") else L   # of = 나레/원음 번역 자막 따로(자수 자가 다르다)
        bad = [(l["id"], c) for l in sel for c in _caps(l) if nchar(c) > mx]
        return not bad, f"자막 덩어리 {mx}자 넘음 {bad}"
    if k == "orig_span":
        if not O:
            return False, "원음 줄 없음"
        l = O[0] if r["which"] == "first" else O[-1]
        s = _orig_sec(l)
        return s <= r["max"], f"{r['which']} 원음 {s:.2f}초 (≤{r['max']})"
    if k == "tts_cps_spread":
        R = cps_spread(d, r, st)
        if R["cv"] is None:
            return False, "나레 줄이 3개 미만 — 편차 못 잼"
        ok = R["cv"] <= r["max"]
        tip = "" if ok else " · 제안 " + " / ".join(f"{x['line']} {x['why']}" for x in R["suggest"][:3])
        return ok, f"줄 예상 cps 변동계수 {R['cv']} (≤{r['max']}){tip}"
    if k == "beats":
        got = beats_count(d, r)
        bad = [f"{b['name']} {len(got[b['name']])}줄({b['min']}~{b['max']})" for b in r["beats"] if not b["min"] <= len(got[b["name"]]) <= b["max"]]
        info = " · ".join(f"{n} {v}" for n, v in got.items())
        return not bad, (f"박자 모자람/넘침 {bad} — " if bad else "") + f"줄 머리 박자 {info}"
    if k == "sibling_repeat":
        R = sibling_repeat(Path(d.get("__path__") or ""), d, r, d.get("__version__"))
        ok = not R["bad"]
        return ok, (" / ".join(R["bad"]) if not ok else f"편끼리 첫마디 겹침 최대 {R['worst']}(≤{r['max_share']}) · 비교 {R['n']}편")
    if k in ("head_connectors", "made_candidates"):    # 상위 10편 대조 기계 칸과 같은 자(주인 = bench_compare_script_scene.CONNECTORS·MADE_RE) — 렌더 전에 미리 잰다
        from tools.calcopy import bench_compare_script_scene as BC
        sents = [x.strip() for l in T for x in re.split(r"(?<=[.?!])\s+", txt(l)) if x.strip()]
        if k == "head_connectors":
            hit = [x[:14] for x in sents if any(x.startswith(c) for c in BC.CONNECTORS)]
            sh = round(len(hit) / max(1, len(sents)), 3)
            return sh <= r["max"], f"문장 머리 연결어 {len(hit)}/{len(sents)}={sh} (≤{r['max']}) {hit}"
        hit = [m for x in sents for m in BC.MADE_RE.findall(x)]
        return len(hit) <= r["max"], f"지어냄 후보(숫자·나라·권위 말) {len(hit)}개 (≤{r['max']}) {hit}"
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


# ── 관문 G-1 대본 글 소리 위험(TTS 돈 쓰기 전) — 판 설정 밖 **모든 판 공통** 규칙. 판단 주인 = text_defects 한 곳 ──────────
#   근거 = 10-25 전 편 음성 감사(소리 결함을 낸 대본 줄 ↔ 정상 줄, gate_fixtures/g1_script.json):
#   ① 줄 끝 부호 없음 → 이어 합성한 소리를 줄마다 자를 때 다음 줄로 밀림(98 #75 잇템로그 02 N4·09 N3·11 N3 납품)
#   ② 읽는 글 영문 → 타입캐스트가 건너뜀(감사 'AI'×6·'LED' — narr_verify.latin_lines 가 이 결과를 부른다)
#   ③ 화면 자막 ↔ 읽는 글 엇갈림(98 #17 선우용여 '따라 사 봤는데요' ↔ '하나 사서 따라 해 봤는데요')
#   넣지 않은 것(근거 없음): 줄 안 되풀이(감사 소리 되풀이 2건 = TTS 탓, 대본 글엔 되풀이 0 · 글 되풀이 2건은 소리 정상) · 숫자(읽은 소리 결함 0)
ORIG_KINDS = ("orig", "원음", "원본")
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")
READ_RISKY = re.compile(r"[0-9A-Za-z%]")           # 읽는 글이 화면과 달라도 되는 자리(숫자·영문·기호 읽기 — 제작순서 07 §4)
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"


def _say(l: dict) -> str:
    """TTS 로 보내는 글 — tts 칸, 없으면 text(옛 대본은 text 를 그대로 읽었다)."""
    return str(l.get("tts") or l.get("text") or "").strip()


def narr_lines(d: dict) -> list[dict]:
    """나레(읽는) 줄 — 원음·원본 줄 빼고 읽는 글이 있는 줄."""
    return [l for l in d.get("lines") or [] if isinstance(l, dict) and str(l.get("kind") or "") not in ORIG_KINDS
            and l.get("id") != "O" and not (not l.get("kind") and "said" in l and not l.get("tts")) and _say(l)]


def latin_in(d: dict) -> list[tuple[str, list[str]]]:
    """(판단 주인 — 읽는 글 영문) 읽는 글에 영문이 든 줄 [(줄, 영문 토막)] — 한글 읽기로 바꿔 보낸다(AI → 에이아이, LED → 엘이디)."""
    return [(l.get("id"), LATIN.findall(_say(l))) for l in narr_lines(d) if LATIN.search(_say(l))]


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def _cho(ch: str) -> str:
    return _CHO[(ord(ch) - 0xAC00) // 588] if "가" <= ch <= "힣" else ch


def _shown(l: dict) -> tuple[str | None, list[str]]:
    """화면에 보이는 글(자막 조각을 띄어 이은 것, 조각이 없으면 tts 가 따로 있을 때의 text)과 조각 목록."""
    caps = l.get("caps")
    if isinstance(caps, list) and caps:
        parts = [str((c.get("text") if isinstance(c, dict) else c if isinstance(c, str) else "") or "") for c in caps]
        return " ".join(parts), parts
    if l.get("tts") and l.get("text"):
        return str(l["text"]), []
    return None, []


def shown_not_said(shown: str, say: str) -> list[str]:
    """화면 글의 낱말 가운데 **읽는 글에 순서대로 안 나오는 것**. 읽는 글에만 있는 말(자막을 줄이며 뺀 연결어·조사 — 98 #19)은 허용.
    허용(결함 아님): 숫자·영문·기호가 든 낱말(읽기로 바뀜) · 띄어쓰기·부호 · 낱말 끝 1~2자 차이(조사·어미 '살린'↔'살려낸', '들었대요'↔'들었다는데요') ·
    한 글자 낱말의 초성 같음('것'↔'거', '걍'↔'그냥') · 이름 발음 고침에 붙는 말('방송인 ○○ 씨' — 읽는 글에만 있으니 허용 쪽)."""
    hay = _norm(say)
    pos, miss = 0, []
    for w in re.split(r"[\s/]+", shown):
        n = _norm(w)
        if not n or READ_RISKY.search(w):
            continue
        k = hay.find(n, pos)
        if k < 0:                        # 낱말 끝 1~2자(조사·어미)만 다르면 같은 낱말
            for cut in range(1, min(2, len(n) - 1) + 1):
                k = hay.find(n[:-cut], pos)
                if k >= 0:
                    n = n[:-cut]; break
        if k < 0 and len(n) == 1 and pos < len(hay) and _cho(hay[pos]) == _cho(n):
            k = pos
        if k < 0:
            miss.append(w)
            continue
        pos = k + len(n)
    return miss


def text_defects(d: dict, joined: bool = True) -> list[dict]:
    """(판단 주인 — 관문 G-1) 대본 글만 보고 TTS 전에 막는 소리·자막 결함 [{rule, line, why}] (빈 목록 = 통과).
    joined = 나레 줄을 이어 한 번에 합성하고 글자 시각으로 줄마다 자르는 대본(최상위 lines — render_bench·render_itssum 길).
    샥탬 final.lines 대본(줄마다 따로 합성)은 joined=False 라 줄 끝 부호 규칙을 안 건다."""
    from tools.calcopy.engine import narr_align as NA
    out = []
    N = narr_lines(d)
    T = [l for l in N if l.get("kind") == "tts"]
    if joined:
        for l in T[:-1]:
            if not NA.ends_with_mark(_say(l)):
                out.append({"rule": "end_mark", "line": l.get("id"),
                            "why": f"줄 끝 문장부호 없음 '…{_say(l)[-12:]}' — 이어 합성한 소리를 줄마다 자를 때 다음 줄로 밀린다(98 #75). 끝에 쉼표·마침표"})
    for lid, toks in latin_in(d):
        out.append({"rule": "latin", "line": lid,
                    "why": f"읽는 글에 영문 {toks} — 타입캐스트가 건너뛴다(감사 'AI'·'LED' 7곳). 한글 읽기로(AI → 에이아이, 자막은 원문)"})
    for l in N:
        shown, parts = _shown(l)
        if shown is None:
            continue
        miss_t = shown_not_said(shown, str(l["text"])) if parts and l.get("tts") and l.get("text") else []
        if miss_t:     # 화면 글(text) 칸에 읽기('육십칠 퍼센트')를 적은 대본도 있어 숫자·영문 낱말은 같은 자로 넘긴다(옛 rules.caps_vs_tts 의 글자 그대로 비교는 3편 오검출)
            out.append({"rule": "caps_text", "line": l.get("id"),
                        "why": f"자막 조각을 이으면 '{shown}' — 화면 글(text) '{l['text']}' 에 없는 {miss_t}"})
        miss = shown_not_said(shown, _say(l))
        if miss:
            out.append({"rule": "caps_say", "line": l.get("id"),
                        "why": f"자막 {miss} 를 목소리가 안 읽는다 — 화면 '{shown}' ↔ 목소리 '{_say(l)}'(98 #17: 자막은 읽는 말 그대로, 발음 고침만 다르게)"})
    return out


# ── 대체(비슷한) 제품 밝히기 — 판 설정 밖 **모든 판 공통**. 판단 주인 = alt_disclosed 한 곳 ──────────────────────
#   사장님 10-25 "쿠팡에 같은 제품이 없으면 비슷한 제품으로 가되, 영상에서 분명히 말해야 한다"(제작순서 03 · rules.PRODUCT_TALK alt).
#   대본.json 의 product_mode(exact·named·alt·given — 03 제품 판정, 회원 flow 는 st.product.mode 를 넣는다)가 'alt' 일 때만 잰다.
#   목소리(읽는 글)로 '같은 제품이 아니다'(똑같은 건 없어서·같은 제품은 아니고) 또는 '비슷한 걸/제품'을 말하는 줄이 하나는 있어야 한다.
ALT_SAY = re.compile(r"(똑\s*같은|같은)\s*(제품|건|게|거|걸|것)\s*[은는이가을]?\s*(없|아니|아닌|못\s*찾)|비슷한\s*(걸|거|것|제품|게|건|[^.,!?]{1,12}?(으로|로|을|를))")


def alt_disclosed(d: dict) -> dict | None:
    """(판단 주인) product_mode 'alt' 대본에 '같은 제품이 아니라 비슷한 제품' 이라고 말하는 나레 줄이 있나 → 걸리면 {rule, line, why}, 아니면 None."""
    if str(d.get("product_mode") or "") != "alt":
        return None
    hit = [l.get("id") for l in narr_lines(d) if ALT_SAY.search(_say(l))]
    if hit:
        return None
    return {"rule": "alt_say", "line": None,
            "why": "product_mode alt(쿠팡에 같은 제품 없음 → 비슷한 제품)인데 목소리로 그걸 밝히는 줄이 없다 — "
                   "예 '영상 보고 쿠팡에서 찾아봤는데 똑같은 건 없어서 비슷한 걸로 써 봤어요'(제작순서 03 · 사장님 10-25)"}


# ── 박자(고조·반전) 세기 · 편끼리 첫마디 겹침 — 판 설정 script.audit 규칙 'beats'·'sibling_repeat' ─────────────────
#   사장님 10-25(규칙서 숏템템플릿 §2 8·8-1·8-2): 편마다 같은 틀 반복 금지(작품6·7·8 이 8줄 역할·줄 머리 말이 똑같았다) ·
#   고조 2~3 · 반전 1~2. 기준 숫자·연결어 무늬는 판 설정에만(여기서 정하지 않는다). 판단 주인 = beat_of · sibling_repeat.
def _head(text: str, n: int) -> str:
    return _norm(text)[:n]


def beat_of(text: str, beats: list[dict], head_chars: int = 16, max_start: int = 4) -> str | None:
    """(판단 주인 — 줄 박자) 줄 머리(공백·부호 뺀 앞 head_chars 자)에서 판 beats 무늬가 **앞 max_start 자 안에서 시작**하면 그 박자 이름
    (목록 순서 = 우선) / 없으면 None. '이게 진짜 말도 안 되는 게'(4자 뒤 시작)는 박자, '화력이 세서 심지어 …'(5자 뒤)는 줄 중간 말이라 아니다.
    역할 칸(role)은 쓴 사람이 붙인 이름이라 믿지 않고 글로 잰다(points_check 와 같은 생각)."""
    h = _head(text, head_chars)
    for b in beats:
        m = re.search(b["pattern"], h)
        if m and m.start() <= max_start:
            return b["name"]
    return None


def beats_count(d: dict, r: dict) -> dict:
    """나레 줄(첫 줄 = 제목 줄 뺌)마다 beat_of → {박자 이름: [줄 id…]}."""
    out = {b["name"]: [] for b in r["beats"]}
    for k, l in enumerate(narr_lines(d)):
        if k == 0 and r.get("skip_first", True):
            continue
        b = beat_of(_say(l) if not l.get("text") else l["text"], r["beats"], int(r.get("head_chars", 16)), int(r.get("max_start", 4)))
        if b:
            out[b].append(l.get("id", k))
    return out


def _channel_root(path: Path) -> Path:
    """편 폴더들을 담은 채널 폴더 — channel/<slug>, 없으면(시험 등) 대본 폴더의 부모."""
    p = Path(path).resolve()
    for a in p.parents:
        if a.parent.name == "channel":
            return a
    return p.parent.parent


def _same_item(a: dict, b: dict) -> bool:
    """같은 제품의 변형 판(작품9 원음 A·B·C)은 서로 비교하지 않는다 — 쿠팡 상품번호 또는 topic 이 같으면 같은 편."""
    pa, pb = (a.get("coupang") or {}).get("product_id"), (b.get("coupang") or {}).get("product_id")
    if pa and pb and str(pa) == str(pb):
        return True
    return bool(a.get("topic")) and a.get("topic") == b.get("topic")


def siblings(path: Path, d: dict, version: str, only_preset: bool = False, versions: list | None = None) -> list[tuple[Path, dict]]:
    """같은 채널 폴더 안의 다른 편 대본 중 같은 판(version_of)인 것 — 같은 제품 변형·자기 자신 제외(only_preset = preset 칸 있는 작품 대본끼리만)."""
    me, out = Path(path).resolve(), []
    root = _channel_root(path)
    for p in sorted(root.glob("**/대본.json")):
        if p.resolve() == me:
            continue
        try:
            o = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(o, dict) or version_of(p, None, o) not in (versions or [version]) or _same_item(d, o):
            continue
        if only_preset and not o.get("preset"):
            continue
        out.append((p, as_lines(o)))
    return out


def sibling_repeat(path: Path, d: dict, r: dict, version: str | None) -> dict:
    """(판단 주인 — 편끼리 첫마디 겹침) 이 편 나레 줄 머리(앞 head_chars 자) 가운데 다른 편 줄 머리에도 있는 비율의 최대(편 하나와 견줌)
    + 첫 줄 앞 first_chars 자가 같은 편 + 줄 역할 순서가 통째로 같은 편. 반환 {worst, n, bad[], pairs[]}."""
    if not path or not Path(path).exists():
        return {"worst": 0.0, "n": 0, "bad": [], "pairs": []}
    n, fc = int(r.get("head_chars", 4)), int(r.get("first_chars", 12))
    mine = [_say(l) if not l.get("text") else l["text"] for l in narr_lines(d)]
    heads = [_head(t, n) for t in mine if _head(t, n)]
    roles = [str(l.get("role") or "") for l in d.get("lines") or []]
    worst, bad, pairs = 0.0, [], []
    v0 = version or version_of(Path(path), None, d)
    sib = siblings(path, d, v0, only_preset=r.get("scope") == "preset", versions=r.get("versions"))   # versions = 같은 채널의 옛 판까지 견줄 때(이븐쇼핑판 ↔ 재미썸홈판 작품)
    for p, o in sib:
        other = [_say(l) if not l.get("text") else l["text"] for l in narr_lines(o)]
        oh = {_head(t, n) for t in other}
        same = [h for h in heads if h in oh]
        sh = round(len(same) / max(1, len(heads)), 3)
        name = p.parent.name
        pairs.append({"doc": name, "share": sh, "same": same})
        if sh > worst:
            worst = sh
        if sh > float(r["max_share"]) + 1e-9:
            bad.append(f"'{name}'와 줄 첫마디 {len(same)}/{len(heads)}={sh} 겹침(≤{r['max_share']}) {same} — 연결어 틀을 돌려 쓴다(설명서 '돌림')")
        if mine and other and fc and _head(mine[0], fc) == _head(other[0], fc):
            bad.append(f"'{name}'와 첫 줄 앞 {fc}자 같음 '{mine[0][:20]}'")
        o_roles = [str(l.get("role") or "") for l in o.get("lines") or []]
        if r.get("roles_same") is False and any(roles) and roles == o_roles:
            bad.append(f"'{name}'와 줄 역할 순서가 통째로 같다 {roles}")
    return {"worst": worst, "n": len(sib), "bad": bad, "pairs": sorted(pairs, key=lambda x: -x["share"])[:5]}


def audit(path: Path, version: str | None = None) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    d = as_lines(raw)
    v = version_of(Path(path), version, raw)
    d = {**d, "__path__": str(path), "__version__": v}       # 편끼리 규칙(sibling_repeat)이 자기 자리·판을 안다
    st = ST.load(v)
    lines = tts_lines(d)
    res = {"file": str(path), "version": v, "n_lines": len(lines), "chars": sum(nchar(l["text"]) for l in lines), "rules": []}
    ok = True
    rules = list(st["script"].get("audit") or [])
    if not any(r.get("kind") == "tts_cps_spread" for r in rules) and speech_rule(st):
        rules.append(speech_rule(st))
    for r in rules:
        if r.get("scope") == "preset" and not raw.get("preset"):      # 'preset' = preset_make 작품 대본만(채널 폴더 작품N — 하이브리드 판 대본은 안 잰다)
            continue
        if r["kind"] == "engine":
            e = engine(r["name"], d, lines, tuple(r.get("off") or ()))
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
    for x in text_defects(d, joined=bool(raw.get("lines"))):     # 관문 G-1 — 판 설정과 상관없이 모든 판
        res["rules"].append({"kind": "text:" + x["rule"], "ok": False, "why": f"{x['line']} {x['why']}"}); ok = False
    ad = alt_disclosed(d)     # 대체 제품 밝히기 — 판과 상관없이 모든 판
    if ad:
        res["rules"].append({"kind": "product:" + ad["rule"], "ok": False, "why": ad["why"]}); ok = False
    res["narr"] = [SF.narr_rules(l["text"]) for l in lines]
    res["ok"] = bool(ok)
    return res


def fit_model(pattern: str) -> dict:
    """렌더 자막표의 나레 줄(첫 조각 t0 ~ 끝 조각 t1)로 LINE_MODEL 을 다시 맞춘다 — 최소제곱. 결과를 보고 LINE_MODEL 을 근거 줄과 같이 손으로 고친다."""
    import glob
    import numpy as np
    X, Y, n_ep = [], [], 0
    for f in sorted(glob.glob(pattern)):
        rows = [r for r in json.loads(Path(f).read_text(encoding="utf-8")).get("rows") or [] if (r.get("speaker") or r.get("kind")) == "narr"]
        n_ep += bool(rows)
        by: dict = {}
        for r in rows:
            by.setdefault(r.get("line"), []).append(r)
        for v in by.values():
            t = " ".join(x.get("text") or "" for x in v)
            X.append([1, nchar(t), _punct_in(t)]); Y.append(float(v[-1]["t1"]) - float(v[0]["t0"]))
    X, Y = np.array(X, float), np.array(Y, float)
    co, *_ = np.linalg.lstsq(X, Y, rcond=None)
    r2 = 1 - float(((Y - X @ co) ** 2).sum()) / float(((Y - Y.mean()) ** 2).sum())
    return {"episodes": n_ep, "lines": len(Y), "r2": round(r2, 3), **dict(zip(("base", "per_char", "punct"), (round(float(c), 3) for c in co)))}


def main():
    args = sys.argv[1:]
    if args[:1] == ["fit-model"]:
        print(json.dumps(fit_model(args[1]), ensure_ascii=False))
        return 0
    if args[:1] == ["text-scan"]:     # 관문 G-1 전수 훑기: text-scan "channel/**/대본.json" ["C:/숏템_칼카피/**/대본.json" …] — 규칙별 줄·편 수 + 걸린 줄
        import collections
        import glob
        n, cnt, docs = 0, collections.Counter(), collections.defaultdict(set)
        for pat in args[1:]:
            for f in sorted(glob.glob(pat, recursive=True)):
                try:
                    raw = json.loads(Path(f).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if not isinstance(raw, dict):
                    continue
                n += 1
                for x in text_defects(as_lines(raw), joined=bool(raw.get("lines"))):
                    cnt[x["rule"]] += 1; docs[x["rule"]].add(f)
                    print(f"{f} | {x['rule']} | {x['line']} | {x['why'][:160]}")
        print(json.dumps({"docs": n, "lines": dict(cnt), "docs_hit": {k: len(v) for k, v in docs.items()}}, ensure_ascii=False))
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
