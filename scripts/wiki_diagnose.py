#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wiki_diagnose.py — 종목 페이지를 스키마와 대조해 빈칸·stale 리스트만 출력.

1단계 MVP 철칙: 채우지 않는다. 진단만 한다.
사람이 진단 결과를 보고 "그릇이 적절한가"를 먼저 검증한다.

사용:
  python scripts/wiki_diagnose.py wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md
  python scripts/wiki_diagnose.py "wiki/L5_섹터/반도체/stock/*.md"
"""
import re
import sys
import glob
import argparse
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import yaml
except ImportError:
    print("PyYAML 필요 → pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "wiki" / "_schema" / "stock_page_schema.yaml"
OUT_DIR = ROOT / "wiki" / "_diagnostic"

DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
HEAD_RE = re.compile(r"^(#{1,3})\s")
CALLOUT_RE = re.compile(r"^>\s*\[!\w+\]")  # > [!NOTE] 제목 형태 콜아웃도 의사 헤더로 인식
TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|?\s*$")


def latest_date(text):
    ds = []
    for y, m, d in DATE_RE.findall(text):
        try:
            ds.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    return max(ds) if ds else None


def split_sections(md):
    """헤더 단위로 분해. 각 섹션 body = 다음 동급↑ 헤더 직전까지."""
    lines = md.splitlines()
    heads = []
    for i, ln in enumerate(lines):
        m = HEAD_RE.match(ln)
        if m:
            heads.append((i, len(m.group(1)), ln))
            continue
        if CALLOUT_RE.match(ln):
            heads.append((i, 9, ln))  # 콜아웃 = 깊은 레벨(항상 하위 섹션)
    secs = []
    for idx, (i, lvl, ln) in enumerate(heads):
        end = len(lines)
        for j, l2, _ in heads[idx + 1:]:
            if l2 <= lvl:
                end = j
                break
        secs.append({"line": ln, "lvl": lvl, "body": "\n".join(lines[i:end])})
    return secs


def count_table_rows(body):
    """마크다운 테이블 데이터 행 수 (헤더행·구분선 제외)."""
    pipes = 0
    for ln in body.splitlines():
        s = ln.strip()
        if s.startswith("|") and not TABLE_SEP_RE.match(s):
            pipes += 1
    return max(0, pipes - 1)  # 헤더행 1개 차감


def check_cell(cell, secs):
    hp = re.compile(cell["header_pattern"])
    sec = next((s for s in secs if hp.search(s["line"])), None)
    chk = cell["check"]
    t = chk["type"]

    if t == "header_exists":
        return ("OK", "") if sec else ("MISSING", "헤더 없음")
    if sec is None:
        return ("MISSING", "헤더 없음")

    body = sec["body"]
    body_lines = [l for l in body.splitlines()[1:] if l.strip()]

    if t == "block_nonempty":
        ok = len(body_lines) >= 1
    elif t == "min_lines":
        ok = len(body_lines) >= chk["min"]
    elif t == "table_rows":
        ok = count_table_rows(body) >= chk["min"]
    elif t == "subsection_count":
        ok = body.count("\n### ") >= chk["min"]
    else:
        ok = True

    if not ok:
        return ("EMPTY", f"{t} 미달 (요구 {chk.get('min','-')})")

    # stale 판정 (섹션 내 최신 날짜 기준)
    ld = latest_date(body)
    sd = cell.get("stale_days")
    if ld and sd:
        age = (date.today() - ld).days
        if age > sd:
            return ("STALE", f"최신 {ld}, {age}일 경과 (>{sd})")
    return ("OK", "")


ICON = {"MISSING": "🔴", "EMPTY": "🟠", "STALE": "🟡", "OK": "🟢"}


def diagnose(path, cells, tier_map, profiles, default_tier):
    md = Path(path).read_text(encoding="utf-8")
    secs = split_sections(md)
    name = Path(path).stem.replace("stock_", "")
    tier = tier_map.get(name, default_tier)
    req_cells = set(profiles.get(tier, []))
    rows = []
    for c in cells:
        status, note = check_cell(c, secs)
        required = c["id"] in req_cells   # 등급 프로파일이 필수 여부 결정
        rows.append((c["id"], required, status, note))
    return tier, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+", help="페이지 경로 또는 글롭")
    ap.add_argument("--queue", metavar="JSON", help="일감(required 빈칸)을 JSON 큐로 저장 → 능동워커 입력")
    args = ap.parse_args()

    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    cells = schema["cells"]

    paths = []
    for p in args.pages:
        paths.extend(glob.glob(p))
    if not paths:
        print("대상 파일 없음", file=sys.stderr)
        sys.exit(1)

    # 종목 등급 로드 (핫/워치/정적) — 등급별 요구 칸이 다름
    profiles = schema.get("tier_profiles", {})
    default_tier = schema.get("default_tier", "static")
    tiers_path = ROOT / "wiki" / "_schema" / "stock_tiers.yaml"
    tier_map = {}
    if tiers_path.exists():
        td = yaml.safe_load(tiers_path.read_text(encoding="utf-8")) or {}
        for tier, names in td.items():
            if isinstance(names, list):
                for nm in names:
                    tier_map[nm] = tier

    md_lines = [f"# 위키 진단 — 빈칸 리스트 ({date.today()})", ""]
    md_lines.append(f"> 스키마: `{SCHEMA.relative_to(ROOT)}` ({schema['schema_version']}) · 1단계=진단만, 채우지 않음")
    md_lines.append(f"> 대상 {len(paths)}개 페이지 · 등급별 요구칸 적용(핫/워치/정적)")
    md_lines.append("")

    cell_stat = {c["id"]: {"MISSING": 0, "EMPTY": 0, "STALE": 0, "OK": 0} for c in cells}
    tier_count = {}
    page_summaries = []   # (name, tier, issues, rows)
    total_issue = 0

    for path in paths:
        tier, rows = diagnose(path, cells, tier_map, profiles, default_tier)
        name = Path(path).stem.replace("stock_", "")
        tier_count[tier] = tier_count.get(tier, 0) + 1
        issues = [r for r in rows if r[1] and r[2] != "OK"]   # required 칸만 이슈
        total_issue += len(issues)
        page_summaries.append((name, tier, issues, rows))
        for cid, req, status, note in rows:
            cell_stat[cid][status] += 1

    n = len(paths)
    tier_str = " · ".join(f"{t} {c}" for t, c in sorted(tier_count.items()))
    print(f"\n■ 등급 분포: {tier_str}")

    print(f"\n■ 칸별 집계 ({n}개 페이지, 상태 무관 현황)")
    print(f"  {'칸':<14} {'OK':>4} {'MISS':>5} {'EMPTY':>6} {'STALE':>6}")
    for cid, st in cell_stat.items():
        print(f"  {cid:<14} {st['OK']:>4} {st['MISSING']:>5} {st['EMPTY']:>6} {st['STALE']:>6}")

    print(f"\n■ 이슈 페이지 (required 칸 기준)")
    for name, tier, issues, rows in page_summaries:
        if issues:
            tag = " ".join(f"{ICON[s]}{cid}" for cid, req, s, nt in rows if req and s != "OK")
            print(f"  {name:<16} [{tier:<6}] {tag}")

    md_lines.append(f"## 등급 분포\n\n{tier_str}\n")
    md_lines.append("## 칸별 집계 (상태 무관 현황)")
    md_lines.append("")
    md_lines.append("| 칸 | OK | MISSING | EMPTY | STALE |")
    md_lines.append("|----|----|---------|-------|-------|")
    for cid, st in cell_stat.items():
        md_lines.append(f"| {cid} | {st['OK']} | {st['MISSING']} | {st['EMPTY']} | {st['STALE']} |")
    md_lines.append("")
    md_lines.append("## 페이지별 이슈 (required 칸 기준)")
    md_lines.append("")
    for name, tier, issues, rows in page_summaries:
        if not issues:
            continue
        md_lines.append(f"### {name} [{tier}] — 이슈 {len(issues)}")
        for cid, req, status, note in issues:
            md_lines.append(f"- {ICON[status]} **{cid}** {status} {note}")
        md_lines.append("")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{date.today()}_빈칸리스트.md"
    out.write_text("\n".join(md_lines), encoding="utf-8")
    clean = sum(1 for _, _, iss, _ in page_summaries if not iss)
    print(f"\n총 이슈 {total_issue}건 · 무결점 페이지 {clean}/{n} → {out.relative_to(ROOT)}")

    # 능동워커용 일감 큐 (required 빈칸만)
    if args.queue:
        import json
        path_by_name = {Path(p).stem.replace("stock_", ""): p for p in paths}
        queue = []
        for name, tier, issues, rows in page_summaries:
            for cid, req, status, note in issues:
                queue.append({
                    "name": name, "tier": tier, "page": path_by_name.get(name),
                    "cell": cid, "status": status, "note": note,
                })
        Path(args.queue).write_text(
            json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"일감 큐 {len(queue)}건 → {args.queue}")


if __name__ == "__main__":
    main()
