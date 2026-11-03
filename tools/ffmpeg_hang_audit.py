# -*- coding: utf-8 -*-
"""ffmpeg 무한 멈춤 꼴 전수 점검(관제 285 — 10-29 잇템로그 2편 4시간 멈춤 뒤 사장님 "오늘 난 거 말고 점검해서 볼 수 있는 건 없나").

    py tools/ffmpeg_hang_audit.py [--all]        # 위험(HIGH·MID)만 / --all = 안전으로 본 것까지

멈춤 꼴 = 끝없는 입력(-loop 1 · -stream_loop -1 · lavfi color/anullsrc 길이 없음 · tpad clone) 에 기대 끝나는 명령에서
끝을 정해 줄 다른 입력이 0 프레임이 되는 경우. -frames:v·-t 는 **나온 프레임**으로 세므로 입력이 비면 막지 못한다(10-29 실측: -frames:v 25 로도 4시간).
  HIGH = 끝없는 입력 + 다른 입력 앞에 -ss(시작 초가 그 파일 길이를 넘으면 0 프레임) — 시작 초를 길이와 대조하는 검사가 같은 함수에 없으면 위험
  MID  = 끝없는 입력 + 다른 입력이 파일(비어 있을 때만 멈춤)
  각 줄의 '시간 제한' = 그 명령을 부르는 자리에 timeout 이 있나(없으면 멈추면 영원).
판정은 코드 모양(AST)만 본다 — 실제로 멈추는지는 재현으로 확인한다(이 도구는 후보를 빠짐없이 뽑는 몫).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ["shopping_shorts", "tools/calcopy", "tools/caption_pack"]
WRAPPERS = {"_run_ffmpeg", "run", "_run", "run_ffmpeg", "_ff", "ff"}
SUBP = {"run", "Popen", "check_output", "check_call", "call"}


def _strs(node) -> list[str]:
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            out.append("".join(v.value if isinstance(v, ast.Constant) else "{}" for v in n.values))
    return out


def _seq(lst: ast.AST) -> list[str]:
    """명령 리스트를 순서대로 — 상수면 값, 아니면 '{}'."""
    if not isinstance(lst, (ast.List, ast.Tuple)):
        return []
    out = []
    for e in lst.elts:
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            out.append(e.value)
        elif isinstance(e, ast.JoinedStr):
            out.append("".join(v.value if isinstance(v, ast.Constant) else "{}" for v in e.values))
        elif isinstance(e, ast.Starred):
            out.append("*" + (ast.unparse(e.value)[:40]))
        else:
            out.append("{" + ast.unparse(e)[:40] + "}")
    return out


def _inputs(seq: list[str]) -> list[tuple[list[str], str]]:
    """명령 → 입력마다 (입력 옵션들, -i 값). 입력 옵션 = 앞 입력 뒤부터 이 -i 앞까지."""
    out, opts = [], []
    i = 1
    while i < len(seq):
        if seq[i] == "-i" and i + 1 < len(seq):
            out.append((opts, seq[i + 1])); opts = []; i += 2; continue
        opts.append(seq[i]); i += 1
    return out


def classify(seq: list[str], text: str) -> tuple[str, list[str]]:
    """끝없는 입력 중 입력 앞 -t(또는 lavfi d=)로 길이를 받은 것은 끝난다. 남은 끝없는 입력이 있고
    다른 입력 앞에 -ss 가 있으면 HIGH(시작 초가 길이를 넘으면 0 프레임 → 영원히), 다른 입력이 있으면 MID."""
    why, unbounded = [], []
    ins = _inputs(seq)
    for opts, src in ins:
        kind = ""
        if any(opts[k] == "-loop" and opts[k + 1] == "1" for k in range(len(opts) - 1)):
            kind = "-loop 1"
        elif any(opts[k] == "-stream_loop" and opts[k + 1] in ("-1", "{-1}") for k in range(len(opts) - 1)):
            kind = "-stream_loop -1"
        elif "lavfi" in opts and any(k in src for k in ("color", "anullsrc", "sine", "nullsrc")) and "d=" not in src and "duration" not in src:
            kind = "lavfi 길이 없음"
        if not kind:
            continue
        if "-t" in opts or "-to" in opts:
            why.append(kind + "(입력 앞 -t 로 끝남)")
            continue
        unbounded.append(kind)
    if "stop_mode=clone" in text and "stop_duration" not in text:
        unbounded.append("tpad clone 길이 없음")
    if not unbounded:
        return "", why
    why = unbounded + why
    if any(s.startswith("*") for s in seq):
        why.append("입력 일부가 변수 목록(*)")
    finite = [(o, s) for o, s in ins if not any(x in o for x in ("-loop", "-stream_loop", "lavfi"))]
    if any("-ss" in o for o, s in finite):
        return "HIGH", why + ["-ss 뒤 입력이 끝을 정함"]
    if finite or any(s.startswith("*") for s in seq):
        return "MID", why + ["다른 입력이 끝을 정함"]
    return "LOW", why + ["끝없는 입력만(-t·-frames 로 끝남)"]


def scan_file(p: Path) -> list[dict]:
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    rows = []
    funcs = {}
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(f):
                funcs.setdefault(id(n), f)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")
        if name not in WRAPPERS | SUBP or not node.args:
            continue
        a0 = node.args[0]
        seq = _seq(a0)
        if not seq or "ffmpeg" not in seq[0]:
            continue
        fn = funcs.get(id(node))
        text = " ".join(_strs(a0))
        # *변수 = 같은 함수 안에서 그 이름에 넣은 목록을 풀어 본다(10-29 사고 자리 scene_style.compose 의 '-loop 1' 은 layer_input 변수에 있었다)
        lists = {}
        for n in ast.walk(fn) if fn else []:
            tgt = n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1 else (n.target if isinstance(n, ast.AugAssign) else None)
            if isinstance(tgt, ast.Name):
                vals = [v for v in ast.walk(n.value) if isinstance(v, (ast.List, ast.Tuple))]
                for v in vals:
                    lists.setdefault(tgt.id, []).append(v)
        ex = []
        for s in seq:
            if s.startswith("*") and s[1:] in lists:
                for v in lists[s[1:]]:
                    ex += _seq(v)
                    text += " " + " ".join(_strs(v))
            else:
                ex.append(s)
        seq = ex
        level, why = classify(seq, text)
        direct = isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
        # video_assemble._run_ffmpeg · hybrid.common.run 은 기본 상한(SHORTEM_FFMPEG_TIMEOUT, 관제 285)이 있다 — subprocess 직접 호출만 없다
        has_to = any(k.arg == "timeout" for k in node.keywords) or (not direct and name in ("_run_ffmpeg", "run"))
        fsrc = ast.get_source_segment(p.read_text(encoding="utf-8"), fn) if fn else ""
        guard = bool(fsrc) and any(k in fsrc for k in ("_probe_duration", "probe(", "dur_of(", "count_frames(", "영상보다 길다"))
        rows.append({"file": str(p.relative_to(ROOT)).replace("\\", "/"), "line": node.lineno, "func": fn.name if fn else "-",
                     "level": level or "OK", "why": ", ".join(why), "timeout": has_to, "len_check": guard, "via": name})
    return rows


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    show_all = "--all" in argv
    rows = []
    for d in SCAN:
        for p in sorted((ROOT / d).rglob("*.py")):
            if "tests" in p.parts or "node_modules" in p.parts:
                continue
            rows += scan_file(p)
    order = {"HIGH": 0, "MID": 1, "LOW": 2, "OK": 3}
    rows.sort(key=lambda r: (order[r["level"]], r["file"], r["line"]))
    cnt = {k: sum(r["level"] == k for r in rows) for k in order}
    no_to = sum(not r["timeout"] for r in rows)
    print(f"ffmpeg 명령 {len(rows)}곳 · HIGH {cnt['HIGH']} · MID {cnt['MID']} · LOW {cnt['LOW']} · 끝없는 입력 없음 {cnt['OK']} · 시간 제한 없음 {no_to}곳")
    print("| 등급 | 위치 | 함수 | 끝없는 입력 | 길이 확인 | 시간 제한 |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        if r["level"] in ("HIGH", "MID") or show_all:
            print(f"| {r['level']} | {r['file']}:{r['line']} | {r['func']} | {r['why']} | {'있음' if r['len_check'] else '없음'} | {'있음' if r['timeout'] else '없음'} |")
    return 1 if any(r["level"] == "HIGH" and not r["len_check"] for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
