#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worker_active.py — 능동 리서치 워커 (오케스트레이터).

흐름:
  1. wiki_diagnose.py --queue queue.json   → 일감(required 빈칸) 산출
  2. (Claude/Gemini가 queue.json 의 각 건을 리서치 → results.json)
       results 항목: {name, page, cell, value, source, confidence}
  3. worker_active.py --apply results.json  → 검증 후 통과만 페이지 패치, 미달은 _pending

⚠️ 1단계 안전수칙:
  - claude -p 로 페이지 통째 재작성 금지. 여기서는 '메타(종목코드)' 칸만 헤더 패치.
  - confidence < THRESHOLD 또는 형식검증 실패 → 자동 입력 금지, _pending 적재(오염 방지).
  - 다관점/종합 등 서술 칸은 종합워커(서브에이전트)가 담당. 본 워커는 팩트 칸만.
"""
import re
import sys
import json
import argparse
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "wiki" / "_pending" / "수동확인필요"
DIAG = ROOT / "wiki" / "_diagnostic"
CONF_THRESHOLD = 0.7

# 칸별 형식 검증기 (통과해야 자동 입력)
VALIDATORS = {
    "메타": lambda v: bool(re.fullmatch(r"\d{6}", str(v).strip())),
}

# 칸별 페이지 패치 함수
HEAD_RE = re.compile(r"^#\s+(.+?)(\s*\(.*\))?\s*$")


def patch_meta(page, value):
    """첫 '# 종목명' 헤더에 종목코드 (value) 삽입/치환."""
    p = Path(page)
    lines = p.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        m = HEAD_RE.match(ln)
        if m and not ln.startswith("##"):
            title = m.group(1).strip()
            lines[i] = f"# {title} ({value})"
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
    return False


PATCHERS = {"메타": patch_meta}


def apply_results(results):
    applied, pending = [], []
    for r in results:
        cell = r.get("cell")
        val = r.get("value")
        conf = float(r.get("confidence", 0))
        reason = None

        if conf < CONF_THRESHOLD:
            reason = f"confidence {conf} < {CONF_THRESHOLD}"
        elif cell not in VALIDATORS:
            reason = f"칸 '{cell}' 자동입력 미지원(종합워커 담당)"
        elif not VALIDATORS[cell](val):
            reason = f"형식검증 실패 (value={val!r})"

        if reason:
            pending.append({**r, "reason": reason})
            continue

        if PATCHERS[cell](r["page"], val):
            applied.append(r)
        else:
            pending.append({**r, "reason": "패치 대상 헤더 못 찾음"})
    return applied, pending


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", metavar="JSON", required=True, help="리서치 결과 JSON")
    args = ap.parse_args()

    results = json.loads(Path(args.apply).read_text(encoding="utf-8"))
    applied, pending = apply_results(results)

    print(f"✅ 채움 {len(applied)}건 · ⏸ 보류 {len(pending)}건")
    for r in applied:
        print(f"  ✅ {r['name']:<14} {r['cell']} = {r['value']} ({r.get('source','?')})")
    for r in pending:
        print(f"  ⏸ {r['name']:<14} {r['cell']} — {r['reason']}")

    # 보류 → _pending 적재
    if pending:
        PENDING.mkdir(parents=True, exist_ok=True)
        lines = [f"# 능동워커 보류 — 수동 확인 필요 ({date.today()})", ""]
        lines.append("| 종목 | 칸 | 사유 | 리서치값 | 출처 |")
        lines.append("|------|----|----|--------|------|")
        for r in pending:
            lines.append(f"| {r['name']} | {r['cell']} | {r['reason']} | {r.get('value','')} | {r.get('source','')} |")
        (PENDING / f"{date.today()}_능동워커_보류.md").write_text("\n".join(lines), encoding="utf-8")

    # 처리결과 로그
    DIAG.mkdir(parents=True, exist_ok=True)
    log = [f"# 능동워커 처리결과 ({date.today()})", "",
           f"- 입력 {len(results)}건 · 채움 {len(applied)} · 보류 {len(pending)}", ""]
    for r in applied:
        log.append(f"- ✅ {r['name']} · {r['cell']} = {r['value']} · {r.get('source','?')}")
    for r in pending:
        log.append(f"- ⏸ {r['name']} · {r['cell']} · {r['reason']}")
    (DIAG / f"{date.today()}_능동워커_로그.md").write_text("\n".join(log), encoding="utf-8")
    print(f"→ 로그: wiki/_diagnostic/{date.today()}_능동워커_로그.md")


if __name__ == "__main__":
    main()
