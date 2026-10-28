# -*- coding: utf-8 -*-
"""영향 지도 — 판단의 주인 함수를 고치면 어디까지 번지는지 **도구가** 계산한다(관제 설계 1-3, 카드 002).

왜: 09-26~27 사고의 공통 뿌리는 "고치면 어디까지 번지는지 사람이 그때그때 떠올렸다"는 것. 한 곳만 고치고 캡컷·ZIP·썸네일이
빠지는 일(0순위-A1a)을 규칙 문장이 아니라 finish 가 막는다.

무엇을 하나
  ① 호출 그래프(정적): shopping_shorts 의 .py 는 ast 로 import·호출 이름을, .js/.html 은 `이름(` 정규식으로 뽑아
     "이 함수를 부르는 파일" = 소비처 목록을 만든다.
  ② 소유권 지도(관제/ownership.json)에서 그 함수가 속한 판단의 결과물 노드(소비처 설명)·검사 도구·과금 관여를 붙인다.
  ③ 수리 명세서: 수리 지점 / 같이 봐야 할 소비처 N / 다시 재야 할 검사 / 승인 필요(고객 화면 소비처가 있나) / 함께 병합할 묶음.
  ④ finish 대조: 병합 diff 에서 **주인 함수**가 바뀌었으면, 그 소비처 중 diff 에 없는 파일마다 카드에
     `영향 없음: <파일> — <이유>` 한 줄이 있어야 통과(부분 수리 차단). 없으면 명세서를 찍고 거절한다.
  ⑤ 신선도: 지도에 없는 새 소비처(주인 함수를 새로 부르는 파일)가 생기면 알린다(지도 갱신 요구).

★판단 주인: 소비처 계산은 이 파일의 consumers() 하나. finish(control.finish_gate)는 이걸 부른다.

사용:
    py tools/impact.py spec <함수|파일:함수>          # 수리 명세서
    py tools/impact.py template <함수>               # 카드에 붙일 '영향 없음:' 줄 틀
    py tools/impact.py diff [--base origin/main]      # 지금 워킹트리 변경이 어떤 주인 함수를 건드리고 소비처가 어디인지
"""
import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCOPE_PREFIX = "shopping_shorts/"
SCOPE_SUFFIX = (".py", ".js", ".html")
EXCLUDE = ("/tests/", "/test_", "/node_modules/", "/static/vendor/", "/_t_", "/scripts/")
NO_IMPACT = re.compile(r"영향\s*없음\s*[:：]\s*([^\s—\-–:]+)")


def _git(cwd, *args):
    p = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def in_scope(rel):
    p = rel.replace("\\", "/")
    return p.startswith(SCOPE_PREFIX) and p.endswith(SCOPE_SUFFIX) and not any(x in "/" + p for x in EXCLUDE)


# ── 파일 읽기 (워킹트리 / index / ref) ────────────────────────────────────

def list_files(cwd, ref=None):
    rc, out = _git(cwd, "ls-tree", "-r", "--name-only", ref, "--", SCOPE_PREFIX.rstrip("/")) if ref \
        else _git(cwd, "ls-files", "--", SCOPE_PREFIX.rstrip("/"))
    return [ln.strip() for ln in out.splitlines() if ln.strip() and in_scope(ln.strip())] if rc == 0 else []


def read_file(cwd, rel, ref=None, index=False):
    if ref or index:
        rc, out = _git(cwd, "show", ("%s:%s" % (ref, rel)) if ref else (":%s" % rel))
        return out if rc == 0 else ""
    try:
        return (Path(cwd) / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ── 이름 추출 (순수 함수) ───────────────────────────────────────────────

def py_names(src):
    """→ (정의한 함수 이름 집합, 부르거나 import 한 이름 집합). 파싱 실패면 정규식으로 대충."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return set(re.findall(r"^\s*def\s+(\w+)", src, re.M)), set(re.findall(r"\b(\w+)\s*\(", src))
    defs, uses = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.add(node.name)
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                uses.add(f.id)
            elif isinstance(f, ast.Attribute):
                uses.add(f.attr)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                uses.add(a.name)
        elif isinstance(node, ast.Attribute):
            uses.add(node.attr)          # mod.func 를 인자로 넘기는 경우(함수 참조)
    return defs, uses


def js_names(src):
    defs = set(re.findall(r"\bfunction\s+(\w+)\s*\(", src)) | set(re.findall(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:function\b|\()", src))
    uses = set(re.findall(r"\b(\w+)\s*\(", src))
    return defs, uses


def names_of(rel, src):
    return py_names(src) if rel.endswith(".py") else js_names(src)


def build_index(cwd, ref=None, index=False):
    """{파일: (defs, uses)}"""
    out = {}
    for rel in list_files(cwd, ref):
        out[rel] = names_of(rel, read_file(cwd, rel, ref, index))
    return out


def consumers(idx, func, owner_file):
    """func 를 부르는(정의가 아닌) 파일들 — 주인 파일·같은 이름을 스스로 정의한 파일은 뺀다(두 벌은 ownership_check 의 몫)."""
    owner_file = owner_file.replace("\\", "/")
    out = []
    for rel, (defs, uses) in idx.items():
        if rel == owner_file or func in defs:
            continue
        if func in uses:
            out.append(rel)
    return sorted(out)


# ── 소유권 지도와 붙이기 ─────────────────────────────────────────────────

def owner_functions(own):
    """{함수: (파일, 판단 dict)} — ownership.json 의 '주인' 항목(파일:함수)에서."""
    out = {}
    for j in own.get("판단", []):
        for o in j.get("주인", []):
            if ":" in o:
                f, fn = o.split(":", 1)
                out[fn] = (f.replace("\\", "/"), j)
    return out


def spec(idx, own, func, owner_file=None):
    """수리 명세서 dict. 지도에 없는 함수면 판단 없이 소비처만."""
    of = owner_functions(own)
    if func in of:
        owner_file, j = of[func]
    else:
        j = None
        if owner_file is None:
            cands = [rel for rel, (defs, _u) in idx.items() if func in defs]
            owner_file = cands[0] if len(cands) == 1 else (cands[0] if cands else "")
    cons = consumers(idx, func, owner_file) if owner_file else []
    ui = [c for c in cons if "/static/" in c or "/templates/" in c]
    return {
        "함수": func, "주인 파일": owner_file, "판단": j["이름"] if j else "(지도에 없음 — 새 판단이면 먼저 지도에 적어라)",
        "소비처 파일": cons, "결과물 노드": (j or {}).get("소비처", []), "검사 도구": (j or {}).get("검사도구", ""),
        "과금 관여": bool((j or {}).get("과금")), "고객 화면 소비처": ui,
        "승인": "예(고객 화면 소비처 %d)" % len(ui) if ui else ("예(과금 관여)" if (j or {}).get("과금") else "diff 로 판정"),
    }


def render_spec(s):
    lines = ["■ 수리 명세서 — %s (%s)" % (s["함수"], s["주인 파일"] or "?"),
             "  판단: %s" % s["판단"],
             "  같이 봐야 할 소비처 %d: %s" % (len(s["소비처 파일"]), ", ".join(s["소비처 파일"]) or "-"),
             "  결과물 노드: %s" % (", ".join(s["결과물 노드"]) or "-"),
             "  다시 재야 할 검사: %s" % (s["검사 도구"] or "-"),
             "  승인: %s" % s["승인"],
             "  함께 병합할 묶음: 주인 함수 + 위 소비처 중 실제로 바뀌는 것. 안 바뀌는 소비처는 카드에 '영향 없음: <파일> — 이유'"]
    return "\n".join(lines)


def template(s):
    return "\n".join("영향 없음: %s — <이유>" % c for c in s["소비처 파일"])


# ── finish 대조 ─────────────────────────────────────────────────────────

def changed_py_functions(old_src, new_src, diff_u0):
    """diff 가 닿은 최상위 함수 이름(옛·새 소스 모두) — video_gate 의 판정 함수를 그대로 쓴다(두 벌 금지)."""
    import video_gate as vg
    old_lines, new_lines = vg.diff_changed_lines(diff_u0)
    names = set()
    for src, lines in ((old_src, old_lines), (new_src, new_lines)):
        if not lines:
            continue
        scopes = vg.top_level_scopes(src or "")
        if scopes is None:
            return None
        for ln in lines:
            sc = vg._scope_of(scopes, ln)
            if sc:
                names.add(sc[0])
    return names


def changed_owner_functions(stage, own, changed_files):
    """병합 diff(index vs HEAD)가 건드린 **주인 함수** 목록 → [(함수, 주인 파일)]. .js/.html 주인 파일은 파일이 바뀌면 그 파일의 주인 함수 전부."""
    of = owner_functions(own)
    by_file = {}
    for fn, (f, _j) in of.items():
        by_file.setdefault(f, []).append(fn)
    hit = []
    for rel in changed_files:
        rel = rel.replace("\\", "/")
        if rel not in by_file:
            continue
        if rel.endswith(".py"):
            _, old = _git(stage, "show", "HEAD:%s" % rel)
            _, new = _git(stage, "show", ":%s" % rel)
            _, d = _git(stage, "diff", "--cached", "-U0", "HEAD", "--", rel)
            names = changed_py_functions(old, new, d)
            if names is None:
                hit += [(fn, rel) for fn in by_file[rel]]          # 파싱 실패 → 전부로 본다
            else:
                hit += [(fn, rel) for fn in by_file[rel] if fn in names]
        else:
            hit += [(fn, rel) for fn in by_file[rel]]
    return hit


def no_impact_claims(cards):
    """카드 본문·이력의 '영향 없음: <파일>' → 파일 이름(basename 포함) 집합."""
    out = set()
    for c in cards:
        for m in NO_IMPACT.findall(c.get("body", "") + "\n" + "\n".join(c.get("이력", []))):
            out.add(m.replace("\\", "/"))
    return out


def _claimed(rel, claims):
    return rel in claims or Path(rel).name in claims


def finish_check(stage, own, changed_files, cards, base_ref="HEAD"):
    """→ (fails, notes). 주인 함수가 바뀌었는데 소비처가 diff 에도 카드 '영향 없음' 에도 없으면 fail."""
    fails, notes = [], []
    hits = changed_owner_functions(stage, own, changed_files)
    if not hits:
        return fails, ["영향 지도: 주인 함수 변경 없음"]
    idx_new = build_index(stage, index=True)
    idx_old = build_index(stage, ref=base_ref)
    changed = {c.replace("\\", "/") for c in changed_files}
    claims = no_impact_claims(cards)
    for fn, f in hits:
        s = spec(idx_new, own, fn, f)
        cons = s["소비처 파일"]
        missing = [c for c in cons if c not in changed and not _claimed(c, claims)]
        new_cons = sorted(set(cons) - set(consumers(idx_old, fn, f)))
        notes.append("영향 지도: %s(%s) 소비처 %d · diff 에 %d · 영향 없음 표기 %d" % (
            fn, f, len(cons), sum(1 for c in cons if c in changed), sum(1 for c in cons if _claimed(c, claims))))
        if new_cons:
            notes.append("  ⚠️ 새 소비처(주인 함수를 새로 부른다 — 지도의 소비처·검사에 반영하라): %s" % ", ".join(new_cons))
        if missing:
            fails.append("주인 함수 %s 를 고쳤는데 소비처 %d곳이 diff 에도 카드에도 없다(부분 수리 차단, 관제 1-3):\n%s\n"
                         "    카드에 적어라: py tools/control.py note <번호> \"영향 없음: <파일> — <이유>\"  (틀: py tools/impact.py template %s)\n"
                         "    빠진 소비처: %s" % (fn, len(missing), render_spec(s).replace("\n", "\n    "), fn, ", ".join(missing)))
    return fails, notes


# ── cli ───────────────────────────────────────────────────────────────

def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="영향 지도")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("spec")
    p.add_argument("target", help="함수 또는 파일:함수")
    p = sub.add_parser("template")
    p.add_argument("target")
    p = sub.add_parser("diff")
    p.add_argument("--base", default="origin/main")
    args = ap.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    import ownership_check as oc
    own = oc.load_map(repo) or {"판단": []}
    if args.cmd in ("spec", "template"):
        owner_file, func = (args.target.split(":", 1) if ":" in args.target else (None, args.target))
        idx = build_index(repo)
        s = spec(idx, own, func, owner_file)
        print(render_spec(s) if args.cmd == "spec" else template(s))
        return 0
    rc, out = _git(repo, "diff", "--name-only", args.base)
    changed = [ln.strip() for ln in out.splitlines() if ln.strip()]
    rc, out2 = _git(repo, "diff", "--name-only", "--cached", args.base)
    changed = sorted(set(changed) | {ln.strip() for ln in out2.splitlines() if ln.strip()})
    # 워킹트리 비교: index 대신 파일을 읽는다
    of = owner_functions(own)
    hits = [(fn, f) for fn, (f, _j) in of.items() if f in changed]
    if not hits:
        print("주인 함수 파일 변경 없음 (변경 %d파일)" % len(changed))
        return 0
    idx = build_index(repo)
    for fn, f in hits:
        print(render_spec(spec(idx, own, fn, f)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
