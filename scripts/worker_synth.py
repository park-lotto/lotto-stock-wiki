#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worker_synth.py — 종합 워커 (핫 종목 다관점 갱신).

흐름:
  1. (오케스트레이터가 핫 종목 + 신규 원자 식별)
  2. 원본을 작업 복사본으로 복제 → 서브에이전트(Agent 툴)가 작업본만 Edit
       · 다관점(강세론/신중/충돌/썰) 섹션에 신규 원자 통합
       · 절대 금지: 페이지 통째 재작성, 다른 섹션 임의 수정, stdout 잡담
  3. validate(원본, 작업본) → 파괴 방지 검증 게이트
  4. apply(원본, 작업본)    → 게이트 통과 시에만 백업 후 교체

⚠️ 이전 실패(claude -p 페이지 파괴) 재발 방지:
  - claude -p 단일 호출로 페이지 통째 재작성 금지 → 서브에이전트 + 작업본 격리
  - 게이트 통과 못하면 원본 절대 안 건드림

사용:
  python scripts/worker_synth.py --validate 원본.md 작업본.md
  python scripts/worker_synth.py --apply    원본.md 작업본.md
"""
import re
import sys
import shutil
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 갱신 후에도 반드시 살아있어야 할 섹션(정규식, MULTILINE)
REQUIRED = [
    (r"^#\s.+\(\d{6}\)", "제목+종목코드"),
    (r"^##\s*🟢\s*강세론", "강세론(다관점)"),
    (r"^##\s*증권사 컨센서스", "증권사 컨센서스"),
    (r"^##\s*(📰\s*)?최신 이벤트", "최신 이벤트"),
]


def _schools(text):
    """강세론 섹션 안의 ### 학파 개수."""
    m = re.search(r"^##\s*🟢\s*강세론.*?(?=^##\s)", text, re.M | re.S)
    return m.group(0).count("\n### ") if m else 0


def validate(orig_path, work_path):
    orig = Path(orig_path).read_text(encoding="utf-8")
    work = Path(work_path).read_text(encoding="utf-8")
    fails = []

    # 1) 길이 급감 = 통째 축소/파괴 의심
    if len(work) < len(orig) * 0.85:
        fails.append(f"길이 급감 {len(orig)}→{len(work)}자 (<85%) — 파괴 의심")

    # 2) 필수 섹션 보존
    for pat, label in REQUIRED:
        r = re.compile(pat, re.M)
        if r.search(orig) and not r.search(work):
            fails.append(f"필수 섹션 소실: {label}")

    # 3) '변경요약문만 작성' 사고 패턴 (이전 파괴 사건)
    head = "\n".join(work.splitlines()[:6])
    if re.search(r"(변경|수정|갱신|작업)\s*(요약|사항|내용|완료)", head) and len(work) < len(orig) * 0.5:
        fails.append("변경요약문만 작성 의심 — 이전 파괴 사고 패턴")

    # 4) 강세론 학파 수 보존 (누적 원칙: 줄이지 않는다)
    so, sw = _schools(orig), _schools(work)
    if sw < so:
        fails.append(f"강세론 학파 감소 {so}→{sw} — 누적 보존 위반")

    return fails


def apply(orig_path, work_path):
    bak = Path(str(orig_path) + ".bak")
    shutil.copy(orig_path, bak)
    shutil.copy(work_path, orig_path)
    return bak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", nargs=2, metavar=("ORIG", "WORK"))
    ap.add_argument("--apply", nargs=2, metavar=("ORIG", "WORK"))
    args = ap.parse_args()

    pair = args.validate or args.apply
    if not pair:
        ap.error("--validate 또는 --apply 필요")

    fails = validate(*pair)
    if fails:
        print("❌ 검증 실패 — 원본 적용 거부:")
        for f in fails:
            print("  -", f)
        sys.exit(1)

    print("✅ 검증 통과")
    if args.apply:
        bak = apply(*pair)
        print(f"✅ 원본 반영 완료 (백업: {Path(bak).name})")


if __name__ == "__main__":
    main()
