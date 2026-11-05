# -*- coding: utf-8 -*-
"""칼카피 엔진 v1 결정 파일 — 판단 주인 = 이 폴더의 engine_v1.json 한 곳(관제 319).

사장님 11-06: "우리 엔진에 엄청 많은 내용이 들어 있는데 그걸 참고해서 한다는 거야? 뭘 쓴다는 거야?"
실측: 엔진 코드가 v1.4 규격(`C:\\숏템_칼카피\\_cafe45_cards\\_엔진v1규격.md`)·장부를 읽는 곳 0.
Jev(해결 0.95·뿌리 0.79·위험 0.44, C:\\t\\main_jev\\m1b.out): 규격 §0-1 '코드 닿는 칸' 표를 기계가 읽는 결정 파일 한 곳으로 옮기고,
  엔진(프리셋 기본값·단계 관문·점수판)은 문서가 아니라 이 파일을 읽는다. 문서 §0-1 은 이 파일에서 만든다(`doc`).
  채택 칸 중 주인 함수가 흐름에서 안 불리는 것은 대조 시험이 '안 이음'으로 내 묶음 ③④⑤ 할 일 목록이 된다(`wire`).
Jev(해결 1.00·뿌리 0.79·위험 0.19, C:\\t\\main_jev\\v1gate_q1.out): 관문 합치기 = bench_steps 가 이 파일 행을 같은 꼴(R)로 받아
  evaluate 가 STEPS 와 같이 판정 — 측정 자리(out)·이은 주인이 없는 행은 wait(기록만). out 이 생기면 같은 길로 막는 행이 된다.

행 칸: id · sec(규격 절) · kan(칸) · decision(결정) · gist(§0-1 값 요지 — 문서 생성용 원문 그대로) · value(그 절 원문 줄의 값 전문) ·
  status(§0-1 채택/임시 원문) · state(채택|임시|보류 — 기계용) · jev{conf,root,risk,raw} · refs(근거 N/J/L/보A/보B…) ·
  owner_raw(§0-1 주인 원문) · owners[{file,name,new}] · stage(v1 13단계 키 | '제작' | None) · gate(관문 조건 원문 | None) ·
  bundle(묶음 원문) · src(규격 줄 번호들 — §0-1 줄 + 그 절 원문 줄).
쓰는 법: py -X utf8 -m tools.calcopy.hybrid.engine_v1 import [규격.md] | doc | diff [규격.md] | wire | cov [규격.md] | gates
"""
from __future__ import annotations

import ast
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAL = HERE.parent
DATA = HERE / "engine_v1.json"
DOC_OUT = CAL / "엔진v1_결정표.md"
SPEC = Path(r"C:\숏템_칼카피\_cafe45_cards\_엔진v1규격.md")

# v1 13단계(규격 §1) — 키는 flow_bench 단계 이름 꼴. STAGES 에 아직 없는 것 = bm_pick·bm_voice·bm_s6·bm_freeze
STEP_N = {1: "bm_setup", 2: "bm_pick", 3: "bm_fetch", 4: "bm_tear", 5: "bm_read", 6: "bm_voice", 7: "bm_trial", 8: "bm_pan",
          9: "bm_confirm", 10: "bm_s6", 11: "bm_freeze", 12: "bm_make", 13: "done"}
ALIAS = {"fb": "hybrid/flow_bench.py", "flow_bench": "hybrid/flow_bench.py", "flow": "hybrid/flow.py", "qg": "hybrid/quality_gate.py",
         "sa": "hybrid/script_audit.py", "rb": "hybrid/render_bench.py", "ka": "engine/kal_analyze.py", "kal_analyze": "engine/kal_analyze.py",
         "ps": "engine/preset_save.py", "bm": "engine/bench_member.py", "cf": "engine/channel_find.py", "runner_ops": "hybrid/runner_ops.py",
         "placement": "hybrid/placement.py", "voice_synth": "engine/voice_synth.py", "preset_make": "engine/preset_make.py",
         "claude_cli": "engine/claude_cli.py", "voices": "engine/voices.py", "material_auto": "engine/material_auto.py", "r7": "engine/r7.py",
         "origin_trace": "hybrid/origin_trace.py", "rules": "hybrid/rules.py", "fontmatch": "engine/fontmatch.py",
         "preset_brief": "engine/preset_brief.py", "preset_check": "engine/preset_check.py", "script_audit": "hybrid/script_audit.py"}
HEAD_01 = "| 결정 | 칸 | 값(요지) | 채택/임시 | 주인 함수(파일:함수, 있음/새로) | 묶음 |"


# ---------------------------------------------------------------- 표 읽기(규격 문서)
def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def _sections(lines: list[str]) -> list[tuple[int, int, str]]:
    """(시작 줄 0기준, 끝, 제목) — 제목 줄 사이 구간."""
    hs = [i for i, t in enumerate(lines) if t.startswith("#")]
    return [(s, (hs[k + 1] if k + 1 < len(hs) else len(lines)), lines[s]) for k, s in enumerate(hs)]


def _table(lines, start, end) -> list[tuple[int, list[str]]]:
    rows, head = [], False
    for i in range(start, end):
        t = lines[i]
        if not t.startswith("|"):
            head = False
            continue
        if re.match(r"^\|[\s\-|:]+\|$", t):
            head = True
            continue
        if head:
            rows.append((i + 1, _cells(t)))
    return rows


def sec_rows(lines) -> dict[str, list[tuple[int, list[str]]]]:
    want = {"0-1": "### 0-1.", "0-1a": "#### 0-1a.", "0-2": "### 0-2.", "1": "## 1.", "2-1": "### 2-1.", "3": "## 3.", "4": "## 4.",
            "6": "## 6.", "7-3": "### 7-3.", "8-1": "### 8-1.", "9": "## 9.", "10": "## 10.", "16": "## 16.", "17-1": "### 17-1."}
    out = {}
    for s, e, title in _sections(lines):
        for k, pre in want.items():
            if title.startswith(pre):
                out[k] = _table(lines, s, e)
    return out


def _clean(s: str) -> str:
    return re.sub(r"\*\*", "", s).strip()


_JEV = re.compile(r"해결\s*([01]\.\d+)\s*·\s*뿌리\s*([01]\.\d+)(?:\s*·\s*위험\s*([01]\.\d+))?")
_JEV2 = re.compile(r"([0-9A-Za-z가-힣\-#]+)\s+([01]\.\d\d)·([01]\.\d\d)")
_REF = re.compile(r"(?<![A-Za-z0-9가-힣])(N보\d+|J보\d+|보A-\d+|보B-\d+|L\d{2,3}|N\d{1,3}|J\d{1,3})(?![0-9])")


def parse_jev(*texts: str) -> dict | None:
    """마지막에 적힌 Jev 숫자(규격은 '→ 다시 물음'을 뒤에 붙인다)."""
    best = None
    for t in texts:
        for m in _JEV.finditer(t or ""):
            best = {"conf": float(m[1]), "root": float(m[2]), "risk": float(m[3]) if m[3] else None, "raw": m[0]}
        if best is None:
            for m in _JEV2.finditer(t or ""):
                best = {"conf": float(m[2]), "root": float(m[3]), "risk": None, "raw": m[0]}
    return best


def refs_of(*texts: str) -> list[str]:
    seen = []
    for t in texts:
        for m in _REF.finditer(t or ""):
            if m[1] not in seen:
                seen.append(m[1])
    return seen


def state_of(status: str) -> str:
    s = _clean(status)
    if s.startswith("보류"):
        return "보류"
    if s.startswith("임시") or "임시" in s.split("—")[-1] and not s.startswith("채택") and not s.startswith("결정"):
        return "임시"
    if s.startswith(("채택", "결정", "(v1.4) 됐다 3 에서 뗌")):
        return "채택"
    return "임시"


def _owner_refs(raw: str) -> list[dict]:
    """주인 원문 → [{file, name, new}] (file 은 tools/calcopy 기준, name None = 모듈만 — 함수 이름 없음)."""
    if not raw or raw.startswith(("주인 함수 칸 없음", "—", "칸 주인", "기존")):
        return []
    out = []
    for part in re.split(r"\s+[·+]\s+|\s*→\s*", raw):
        p = _clean(part)
        new = bool(re.search(r"새로|\(새\)|^새 ", p))
        p2 = re.sub(r"^새\s+", "", p)
        m = re.match(r"((?:engine|hybrid)/\w+\.py)[:.]?([A-Za-z_]\w*(?:·[A-Za-z_]\w*)*)?", p2) or \
            re.match(r"(?:hybrid/|engine/)?([a-z_]+)[.:]([A-Za-z_]\w*(?:·[A-Za-z_]\w*)*)", p2)
        if m and m[1].endswith(".py"):
            f, names = m[1], m[2]
        elif m and m[1] in ALIAS:
            f, names = ALIAS[m[1]], m[2]
        else:
            m2 = re.match(r"([A-Za-z_]\w*)", p2)
            tok = m2[1] if m2 else ""
            if tok in ALIAS:
                f, names = ALIAS[tok], None
            elif tok.startswith("bm_") or tok in ("seg_snap", "channel_why", "spend"):
                f, names = ("hybrid/flow_bench.py" if tok.startswith("bm_") else None), tok
            else:
                continue
        for n in (names.split("·") if names else [None]):
            if f and n is None and re.search(r"(?:곁|안)\s*(?:history|lang|틀|color|알려진)", p2):
                pass
            out.append({"file": f, "name": n, "new": new})
    return out


def _stage(kan: str, decision: str, bundle: str) -> str | None:
    for t in (kan, decision):
        m = re.search(r"§1\s*#(\d+)", t) or re.search(r"(?:^|[ ·(])#(\d+)\s+(?:bm_|setup|done)", t)
        if m and int(m[1]) in STEP_N:
            return STEP_N[int(m[1])]
        m = re.search(r"단계\s+(\d+)\s", t)
        if m and int(m[1]) in STEP_N:
            return STEP_N[int(m[1])]
    for t in (kan, bundle, decision):
        for name in re.findall(r"bm_[a-z0-9]+|\bsetup\b|\bdone\b", t):
            name = {"setup": "bm_setup", "bm_panbokki": "bm_pan"}.get(name, name)
            if name in STEP_N.values():
                return name
    if "제작·시험" in bundle or "제작" in bundle:
        return "제작"
    if "§7-3" in kan:
        return "bm_s6"
    if kan.startswith("§6"):
        return "bm_freeze"
    return None


def _find_src(kan: str, decision: str, S: dict) -> tuple[str | None, int | None, list[str]]:
    """§0-1 줄 → 그 절 원문 줄(절 키, 줄 번호, 칸)."""
    k = _clean(kan)
    d = _clean(decision)

    def first(sec, pred):
        for ln, c in S.get(sec, []):
            if pred(_clean(c[0]) if c else "", c):
                return sec, ln, c
        return None, None, []
    m = re.match(r"새 규칙 (?:보충 )?(\S+)", d)
    if m:
        key = m[1]
        return first("16", lambda a, c: re.split(r"[ ·]", a.replace("보충 ", ""))[0] == key.split("·")[0])
    m = re.match(r"§1 #(\d+)", k)
    if m:
        return first("1", lambda a, c: a == m[1])
    m = re.match(r"§4 #(\d+)", k)
    if m:
        return first("4", lambda a, c: a == m[1])
    if k.startswith("§3 "):
        key = k[3:].strip()
        return first("3", lambda a, c: a.startswith(key) or key in a)
    if k == "§6":
        key = d[3:].rstrip("…").strip()
        return first("6", lambda a, c: a.startswith(key) or key.startswith(a))
    if k == "§7-3":
        key = d[5:].strip()
        return first("7-3", lambda a, c: a == key or a.startswith(key.split(" ")[0]))
    if k == "§8-1":
        key = re.sub(r"^§8\s+", "", d)
        return first("8-1", lambda a, c: a == key or a.startswith(key) or key.startswith(a))
    m = re.match(r"코드 보정 (C\d)", d)
    if m:
        return first("0-1a", lambda a, c: a == m[1])
    if "환경 실패" in d:
        return first("0-1a", lambda a, c: a == "C7")
    return None, None, []


def _val_gate(sec: str | None, c: list[str]) -> tuple[str | None, str | None, str]:
    """(값 전문, 관문 조건, 그 절 Jev·근거 글) — 절마다 칸 자리가 다르다(표 머리 실측)."""
    g = lambda i: _clean(c[i]) if len(c) > i and _clean(c[i]) not in ("", "—", "-") else None
    if sec == "1":
        return g(5), g(5), " ".join(c)
    if sec == "3":
        return g(2), None, g(4) or ""
    if sec == "4":
        return g(5), None, " ".join(c[2:5])
    if sec == "6":
        return g(1), g(3), ""
    if sec == "7-3":
        return g(1), g(2), ""
    if sec == "8-1":
        return g(5), g(7), " ".join(c[1:5] + c[6:7])
    if sec == "0-1a":
        return g(2), None, g(4) or ""
    if sec == "16":
        return g(2), g(7), " ".join([c[0]] + c[3:5])
    if sec == "9":
        return g(2), g(3), g(4) or ""
    return None, None, ""


def build(spec: Path = SPEC) -> dict:
    lines = spec.read_text(encoding="utf-8").splitlines()
    S = sec_rows(lines)
    rows = []
    for n, (ln, c) in enumerate(S["0-1"], 1):
        if len(c) < 6:
            raise ValueError(f"§0-1 {ln}줄 칸 수 {len(c)}")
        decision, kan, gist, status, owner_raw, bundle = c[:6]
        sec, sl, sc = _find_src(kan, decision, S)
        value, gate, extra = _val_gate(sec, sc)
        st = state_of(status)
        more = []
        if "§17-2" in kan:      # 새 칸 A — §17-2 본문 + §7-3 점수판 '화면 층' 줄
            more += [i + 1 for i, t in enumerate(lines) if t.startswith("### 17-2.")] + [l for l, cc in S.get("7-3", []) if _clean(cc[0]).startswith("화면 층")]
        if "§17-3" in kan:
            more += [i + 1 for i, t in enumerate(lines) if t.startswith("### 17-3.")]
        rows.append({"id": f"V{n:03d}", "sec": sec or "0-1", "kan": kan, "decision": decision, "gist": gist,
                     "value": value or _clean(gist), "status": status, "state": st,
                     "jev": parse_jev(status, extra), "refs": refs_of(decision, kan, gist, status, " ".join(sc)),
                     "owner_raw": owner_raw, "owners": _owner_refs(owner_raw), "stage": _stage(kan, decision, bundle),
                     "gate": gate if (gate and st != "보류") else gate, "gate_mode": ("막음" if st == "채택" else "기록만") if gate else None,
                     "bundle": bundle, "src": [ln] + ([sl] if sl else []) + more})
    # §0-1 밖 결정 — §9 특수 갈래(언제 그 갈래로 가나 → 더하는 단계·관문). §0-1 에 G10 만 간접으로 있었다.
    for ln, c in S.get("9", []):
        if len(c) < 5 or not _clean(c[0]).startswith("G"):
            continue
        gid = re.match(r"(G\d+[a-z]?)", _clean(c[0]))[1]
        rows.append({"id": f"V9-{gid}", "sec": "9", "kan": f"§9 {gid}", "decision": _clean(c[0]), "gist": _clean(c[1]),
                     "value": _clean(c[2]), "status": "채택(§9 갈래 — v1.1)", "state": "채택", "jev": parse_jev(" ".join(c)),
                     "refs": refs_of(" ".join(c)), "owner_raw": "주인 함수 칸 없음 — 갈래 판정 주인 = bm_tear 칸 하나(§10 P2)",
                     "owners": [], "stage": "bm_tear", "gate": _clean(c[3]), "gate_mode": "기록만", "bundle": "①(branch_of)",
                     "src": [ln], "when": _clean(c[1])})
    # §2-1 사람 부르는 자리 → 자동 결정(엔진 안 멈춤 자리)
    for k, (ln, c) in enumerate(S.get("2-1", []), 1):
        if len(c) < 5:
            continue
        rows.append({"id": f"V2-{k:02d}", "sec": "2-1", "kan": f"§2-1 {_clean(c[0])}", "decision": _clean(c[0]), "gist": _clean(c[1]),
                     "value": _clean(c[2]), "status": f"채택({_clean(c[4])})", "state": "채택", "jev": parse_jev(c[4]),
                     "refs": refs_of(" ".join(c)), "owner_raw": _clean(c[3]), "owners": _owner_refs(_clean(c[3])),
                     "stage": _stage(c[0] + " " + c[3], c[2], ""), "gate": None, "gate_mode": None, "bundle": "②", "src": [ln]})
    return {"spec": str(spec), "spec_lines": len(lines), "made_from": "규격 v1.4 §0-1 156줄 + §9 갈래 + §2-1 자리",
            "count_line_01": next((t for t in lines if t.startswith("줄 수: 전체")), None), "rows": rows}


# ---------------------------------------------------------------- 파일(정본)
@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def rows() -> list[dict]:
    return load()["rows"]


def save(d: dict) -> None:
    DATA.write_bytes((json.dumps(d, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    load.cache_clear()


# ---------------------------------------------------------------- 문서 §0-1 생성(손으로 고치지 않는다)
def render_01() -> str:
    rs = [r for r in rows() if r["id"].startswith("V") and r["id"][1:].isdigit()]
    out = [HEAD_01, "|---|---|---|---|---|---|"]
    out += [f"| {r['decision']} | {r['kan']} | {r['gist']} | {r['status']} | {r['owner_raw']} | {r['bundle']} |" for r in rs]
    return "\n".join(out) + "\n"


def render_full() -> str:
    w = wiring()
    st = {k: sum(1 for r in rows() if r["state"] == k) for k in ("채택", "임시", "보류")}
    out = ["# 엔진 v1 결정표 (자동 생성 — 손으로 고치지 마라)", "",
           f"> 주인 = `tools/calcopy/hybrid/engine_v1.json`. 다시 만들기 `py -X utf8 -m tools.calcopy.hybrid.engine_v1 doc`.",
           f"> 행 {len(rows())} (채택 {st['채택']} · 임시 {st['임시']} · 보류 {st['보류']}) · 채택 주인 이음 {len(w['wired'])} · 안 이음 {len(w['unwired'])} · 주인 미정 {len(w['no_owner'])}",
           "", "## 규격 §0-1 (생성본 — 원문 6칸 그대로)", "", render_01(),
           "## 기계 칸 (단계·관문·주인 대조)", "",
           "| id | 칸 | 상태 | Jev | 단계 | 관문 | 주인(대조) | 묶음 | 근거 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows():
        j = r["jev"]
        js = f"{j['conf']:.2f}·{j['root']:.2f}" + (f"·{j['risk']:.2f}" if j and j.get("risk") is not None else "") if j else "—"
        ow = " · ".join(f"{o['file'] or '?'}:{o['name'] or '(함수 없음)'}={w['state'].get(_okey(o), '?')}" for o in r["owners"]) or "주인 미정"
        gate = (r["gate"] or "—")[:80].replace("|", "\\|")
        out.append(f"| {r['id']} | {r['kan']} | {r['state']} | {js} | {r['stage'] or '—'} | {(r['gate_mode'] or '')} {gate} | {ow} | {r['bundle']} | {', '.join(r['refs'][:8])} |")
    out += ["", "## 안 이음 — 묶음별 할 일(자동 산출)", ""]
    for b, ids in sorted(w["by_bundle"].items()):
        out.append(f"- **{b}** ({len(ids)}): {', '.join(ids)}")
    return "\n".join(out) + "\n"


def diff_01(spec: Path = SPEC) -> dict:
    """생성본 §0-1 표 줄 vs 지금 문서 §0-1 표 줄 — 같으면 문서를 이 파일에서 만든다고 말할 수 있다."""
    lines = spec.read_text(encoding="utf-8").splitlines()
    s, e = next((a, b) for a, b, t in _sections(lines) if t.startswith("### 0-1."))
    doc = [t for t in lines[s:e] if t.startswith("|")]
    gen = render_01().splitlines()
    import difflib
    d = [x for x in difflib.unified_diff(doc, gen, "문서 §0-1", "생성본", lineterm="", n=0) if not x.startswith(("---", "+++", "@@"))]
    return {"doc_rows": len(doc), "gen_rows": len(gen), "diff": d, "same": not d}


# ---------------------------------------------------------------- 대조: 채택 행 주인 함수가 흐름에서 불리나
def _okey(o: dict) -> tuple:
    return (o["file"], o["name"])


@lru_cache(maxsize=None)
def _top_names(f: str) -> frozenset:
    p = CAL / f
    if not p.is_file():
        return frozenset()
    names = set()
    for n in ast.parse(p.read_text(encoding="utf-8")).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return frozenset(names)


@lru_cache(maxsize=1)
def reached_all() -> frozenset:
    """벤치마킹 흐름(bench_steps.reached — flow_bench PHASES + 실행기 명령) ∪ 제작 흐름(flow.PHASES 처리기)에서 정적으로 닿는 (파일, 이름)."""
    from tools.calcopy.hybrid import bench_steps as BS
    got = set(BS.reached())
    fl = str(CAL / "hybrid" / "flow.py")
    roots = []
    for n in ast.walk(ast.parse(Path(fl).read_text(encoding="utf-8"))):
        if isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "PHASES" for x in n.targets) and isinstance(n.value, ast.Dict):
            roots += [(fl, v.id) for v in n.value.values if isinstance(v, ast.Name)]
    todo = [r for r in roots if r not in got]
    while todo:
        k = todo.pop()
        if k in got:
            continue
        got.add(k)
        try:
            todo += [x for x in BS._parse(k[0]).get(k[1], ()) if x not in got]
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
    return frozenset(got)


def owner_state(o: dict) -> str:
    """닿음 | 있음·안 닿음 | 없음(새로) | 함수 이름 없음 | 파일 없음."""
    if not o["file"]:
        return "없음(새로)"
    if not (CAL / o["file"]).is_file():
        return "파일 없음"
    if not o["name"]:
        return "함수 이름 없음"
    if o["name"] not in _top_names(o["file"]):
        return "없음(새로)"
    return "닿음" if (str(CAL / o["file"]), o["name"]) in reached_all() else "있음·안 닿음"


def wiring() -> dict:
    """채택 행 = 주인 함수 하나라도 흐름에서 닿으면 이음. 안 이음 = 주인이 없거나(새로) 있는데 안 불림 → 묶음별 할 일."""
    state, wired, unwired, no_owner, rule = {}, [], [], [], []
    by_bundle: dict[str, list[str]] = {}
    for r in rows():
        for o in r["owners"]:
            state[_okey(o)] = owner_state(o)
        if r["state"] != "채택":
            continue
        if not r["owners"]:
            if r["owner_raw"].startswith("—"):
                rule.append(r["id"])
                continue
            no_owner.append(r["id"])
        elif any(state[_okey(o)] == "닿음" for o in r["owners"]):
            wired.append(r["id"])
            continue
        unwired.append(r["id"])
        by_bundle.setdefault(bundle_key(r["bundle"]), []).append(r["id"])
    return {"wired": wired, "unwired": unwired, "no_owner": no_owner, "rule": rule, "by_bundle": by_bundle, "state": state}


def bundle_key(b: str) -> str:
    b = _clean(b)
    for k in ("①② 코드 보정", "① 코드 보정", "①b", "③a", "③·⑤", "②+", "①②", "①", "②", "③", "④", "⑤"):
        if b.startswith(k):
            return k
    return "— 있음" if b.startswith("—") else b[:10]


# ---------------------------------------------------------------- bench_steps 관문에 더할 행(같은 R 꼴)
def gate_rows_for_bench(phases) -> list[dict]:
    """채택 + 관문 조건 있음 + 단계가 벤치 흐름 단계인 행 → bench_steps.R 꼴. out 이 아직 없어 evaluate 에서 wait(기록만)."""
    out = []
    w = wiring()
    for r in rows():
        if r["state"] != "채택" or not r["gate"] or r["stage"] not in phases:
            continue
        o = next((o for o in r["owners"] if o["file"] and o["name"]), None)
        why = "주인 함수 흐름에서 닿음 — 산출물 자리(out) 아직 없음" if r["id"] in w["wired"] else "결정 파일 행 — 주인 함수 안 이음(" + bundle_key(r["bundle"]) + ")"
        out.append({"id": r["id"], "phase": r["stage"], "slot": r["decision"][:40], "owner": f"{o['file']}:{o['name']}" if o else None,
                    "out": r.get("out"), "check": tuple(r["check"]) if r.get("check") else ("v1",), "doc": [], "wait": {"kind": "함수" if r["id"] not in w["wired"] else "칸", "why": why},
                    "none": None, "at": None, "note": f"엔진 v1 {r['id']} — {r['gate'][:60]}", "v1": True})
    return out


# ---------------------------------------------------------------- 원문 덮임
def coverage(spec: Path = SPEC) -> dict:
    """결정 표가 있는 절의 표 줄 중 결정 파일 행이 src 로 가리키는 비율 + 문서 전체 비지 않은 줄 비율."""
    lines = spec.read_text(encoding="utf-8").splitlines()
    S = sec_rows(lines)
    src = {x for r in rows() for x in r["src"]}
    per = {}
    for k in ("0-1", "0-1a", "1", "2-1", "3", "4", "6", "7-3", "8-1", "9", "16"):
        lns = [ln for ln, c in S.get(k, [])]
        per[k] = {"rows": len(lns), "covered": sum(1 for x in lns if x in src), "miss": [x for x in lns if x not in src]}
    tot = sum(v["rows"] for v in per.values())
    cov = sum(v["covered"] for v in per.values())
    content = sum(1 for t in lines if t.strip())
    return {"per": per, "rows": tot, "covered": cov, "pct": round(100 * cov / max(1, tot), 1),
            "doc_nonempty": content, "doc_pct": round(100 * len(src) / max(1, content), 1)}


def main(argv=None) -> int:
    a = list(argv if argv is not None else sys.argv[1:]) or ["doc"]
    spec = Path(a[1]) if len(a) > 1 else SPEC
    if a[0] == "import":
        save(build(spec))
        print(DATA, len(rows()))
    elif a[0] == "doc":
        DOC_OUT.write_bytes(render_full().encode("utf-8"))
        print(DOC_OUT)
    elif a[0] == "diff":
        d = diff_01(spec)
        print(json.dumps({k: v for k, v in d.items() if k != "diff"}, ensure_ascii=False))
        print("\n".join(d["diff"][:80]))
    elif a[0] == "wire":
        w = wiring()
        print(json.dumps({k: (v if k != "state" else {f"{x[0]}:{x[1]}": s for x, s in v.items()}) for k, v in w.items()}, ensure_ascii=False, indent=1))
    elif a[0] == "cov":
        print(json.dumps(coverage(spec), ensure_ascii=False, indent=1))
    elif a[0] == "gates":
        from tools.calcopy.hybrid import bench_steps as BS
        print(json.dumps([{k: r[k] for k in ("id", "phase", "owner", "wait")} for r in BS.V1], ensure_ascii=False, indent=1))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
