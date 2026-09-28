# -*- coding: utf-8 -*-
"""소유권 검사 — 판단마다 주인 함수는 한 곳. 그 함수의 특징 시그니처가 **지도 밖 파일에 새로** 나타나면 finish 가 막는다.

지도: 관제/ownership.json (판단 → 주인 파일:함수 · 시그니처(정규식) · 소비처 · 검사 도구 · 과금 관여 · 예외{파일: 사유}).
사람이 읽는 표 wiki/rules/판단소유권.md 는 이 JSON 에서 **생성**한다(`render`) — 두 벌로 적지 않는다(0순위-B).

두 가지 모드:
  audit    지금 워킹트리에서 주인 밖 파일에 시그니처가 있는 곳 전부(= 자동 함수전수표). 예외에 적힌 곳은 '예외'로 표시.
  compare  병합 전(base ref) → 병합 후(index)에서 **새로** 생긴 곳만. finish 관문이 이걸 쓴다.
           기존 두 벌(2026-09-27 전수표 21개)은 카드로 순서대로 줄이고, 새 두 벌은 여기서 막는다.

★검사가 무엇을 잡는지 먼저 시험한다(0순위-A1c): tools/test_control.py 가 '주인 밖 파일에 시그니처 심기'로 빨강이 뜨는지 본다.

사용:
    py tools/ownership_check.py audit                 # 지금 폴더
    py tools/ownership_check.py compare --base origin/main
    py tools/ownership_check.py render                # wiki/rules/판단소유권.md 재생성
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MAP_REL = "관제/ownership.json"
TABLE_REL = "wiki/rules/판단소유권.md"
DEFAULT_SCOPE = {"prefixes": ["shopping_shorts/", "tools/"], "suffixes": [".py", ".js", ".html"],
                 "exclude": ["/tests/", "/test_", "/node_modules/", "/static/vendor/", "/_t_"]}


def _git(cwd, *args):
    p = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def load_map(repo, ref=None):
    """지도 → dict. ref 가 있으면 그 커밋의 것(finish 는 origin/main 것을 쓴다 — 트랙이 자기 예외를 늘려 통과하는 길을 막는다). 없으면 None."""
    if ref:
        rc, out = _git(repo, "show", "%s:%s" % (ref, MAP_REL))
        if rc != 0:
            return None
        text = out
    else:
        p = Path(repo) / MAP_REL
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8")
    m = json.loads(text)
    for j in m.get("판단", []):
        j["_owner_files"] = sorted({o.split(":", 1)[0].replace("\\", "/") for o in j.get("주인", [])})
        j["_re"] = [re.compile(s) for s in j.get("시그니처", [])]
    return m


def in_scope(path, scope):
    p = path.replace("\\", "/")
    s = scope or DEFAULT_SCOPE
    if not any(p.startswith(x) for x in s.get("prefixes", [])):
        return False
    if not any(p.endswith(x) for x in s.get("suffixes", [])):
        return False
    return not any(x in ("/" + p) for x in s.get("exclude", []))


def hits_in(text, judgement):
    """파일 내용 → {시그니처: 건수} (0건은 뺀다)."""
    out = {}
    for pat in judgement["_re"]:
        n = len(pat.findall(text or ""))
        if n:
            out[pat.pattern] = n
    return out


def foreign_hits(path, text, own):
    """이 파일이 주인이 아닌 판단의 시그니처를 품고 있나 → [{"file","판단","sig","n","예외"}]."""
    p = path.replace("\\", "/")
    out = []
    for j in own.get("판단", []):
        if p in j["_owner_files"]:
            continue
        for sig, n in hits_in(text, j).items():
            out.append({"file": p, "판단": j["이름"], "sig": sig, "n": n, "예외": (j.get("예외") or {}).get(p, "")})
    return out


# ── audit ───────────────────────────────────────────────────────────

def worktree_files(repo, scope):
    rc, out = _git(repo, "ls-files", "--", *(scope or DEFAULT_SCOPE).get("prefixes", []))
    files = [ln.strip() for ln in out.splitlines() if ln.strip()] if rc == 0 else []
    return [f for f in files if in_scope(f, scope)]


def audit(repo, own):
    rows = []
    for rel in worktree_files(repo, own.get("범위")):
        p = Path(repo) / rel
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rows += foreign_hits(rel, text, own)
    return rows


# ── compare (finish) ───────────────────────────────────────────────────

def _blob_at(cwd, ref, rel):
    """ref 가 None 이면 index(:path) — stage 에서 merge --no-commit 된 내용."""
    rc, out = _git(cwd, "show", ("%s:%s" % (ref, rel)) if ref else (":%s" % rel))
    return out if rc == 0 else ""


def compare_texts(rel, before, after, own):
    """한 파일의 전후 → 새로 생긴 외부 시그니처(전 0건 → 후 1건 이상, 예외 아님)."""
    b = {(h["판단"], h["sig"]) for h in foreign_hits(rel, before, own)}
    out = []
    for h in foreign_hits(rel, after, own):
        if (h["판단"], h["sig"]) in b or h["예외"]:
            continue
        out.append(h)
    return out


def compare_refs(repo, own, base_ref="HEAD", head_index_cwd=None, head_ref=None, changed=None):
    """base_ref 의 파일 vs (index 또는 head_ref) 의 파일 — changed 목록만 본다(새 시그니처는 바뀐 파일에만 생긴다)."""
    cwd = head_index_cwd or repo
    if changed is None:
        rc, out = _git(cwd, "diff", "--cached", "--name-only", base_ref) if head_ref is None \
            else _git(cwd, "diff", "--name-only", base_ref, head_ref)
        changed = [ln.strip() for ln in out.splitlines() if ln.strip()] if rc == 0 else []
    scope = own.get("범위")
    hits = []
    for rel in changed:
        if not in_scope(rel, scope):
            continue
        before = _blob_at(cwd, base_ref, rel)
        after = _blob_at(cwd, head_ref, rel)
        hits += compare_texts(rel, before, after, own)
    return hits


# ── render (사람이 읽는 표) ──────────────────────────────────────────────

def render_table(own):
    lines = ["# 판단 소유권 지도 (자동 생성 — 원본은 `관제/ownership.json`, `py tools/ownership_check.py render`)", "",
             "원칙: 판단 하나 = 주인 함수 하나. 화면·렌더·캡컷·청소본은 그 함수를 **부른다**. "
             "주인 밖 파일에 시그니처가 새로 생기면 `track.py finish` 가 막는다(관제/ownership.json 예외에 사유를 적어야 통과).", "",
             "| # | 판단 | 주인 함수 | 시그니처 | 소비처 | 검사 도구 | 과금 | 예외(두 벌로 남은 곳 → 카드) |", "|---|---|---|---|---|---|---|---|"]
    for i, j in enumerate(own.get("판단", []), 1):
        exc = "<br>".join("%s — %s" % (k, v) for k, v in (j.get("예외") or {}).items()) or "-"
        lines.append("| %d | %s | %s | `%s` | %s | %s | %s | %s |" % (
            i, j["이름"], "<br>".join("`%s`" % o for o in j.get("주인", [])),
            "` `".join(s.replace("|", "\\|") for s in j.get("시그니처", [])),
            ", ".join(j.get("소비처", [])) or "-", j.get("검사도구", "-") or "-", "예" if j.get("과금") else "-", exc))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="소유권 검사")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("audit")
    p = sub.add_parser("compare")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--head", default=None, help="비교할 ref(없으면 index)")
    sub.add_parser("render")
    args = ap.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    own = load_map(repo)
    if own is None:
        print("지도가 없다: %s" % MAP_REL, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
    if args.cmd == "audit":
        rows = audit(repo, own)
        by = {}
        for r in rows:
            by.setdefault(r["판단"], []).append(r)
        for name in by:
            print("■ %s" % name)
            for r in by[name]:
                print("   %s  %s ×%d%s" % (r["file"], r["sig"], r["n"], ("  [예외: %s]" % r["예외"]) if r["예외"] else "  ★두 벌 의심"))
        print("\n== 판단 %d개 · 주인 밖 시그니처 %d곳(예외 %d)" % (len(own.get("판단", [])), len(rows), sum(1 for r in rows if r["예외"])))
        return 0
    if args.cmd == "compare":
        hits = compare_refs(repo, own, base_ref=args.base, head_ref=args.head)
        for h in hits:
            print("★새 두 벌: %s ← %s (%s)" % (h["file"], h["판단"], h["sig"]))
        print("== 새로 생긴 주인 밖 시그니처 %d곳" % len(hits))
        return 1 if hits else 0
    if args.cmd == "render":
        (repo / TABLE_REL).write_text(render_table(own), encoding="utf-8")
        print("생성: %s" % TABLE_REL)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
