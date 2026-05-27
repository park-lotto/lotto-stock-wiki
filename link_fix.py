#!/usr/bin/env python3
"""
link_fix.py — wiki 내 종목명을 [[stock_종목명|display]] 링크로 표준화
사용법: python link_fix.py
결과:  wiki/L5_섹터/ 내 모든 .md 파일
       종목명 (6자리코드) → [[stock_종목명|종목명 (코드)]]
       밸류체인 텍스트 내 종목명도 동일 변환
"""
import re
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT     = Path(__file__).parent
WIKI     = ROOT / "wiki" / "L5_섹터"
MAP_FILE = ROOT / "sector_map.json"

smap   = json.loads(MAP_FILE.read_text(encoding="utf-8"))
known  = {k for k in smap if not k.startswith("_")}
# 긴 이름 먼저 — 부분 매치 방지 (예: "LS" 전에 "LS ELECTRIC" 처리)
names_sorted = sorted(known, key=len, reverse=True)

counts = {"files": 0, "links": 0}


def linkify(text: str) -> tuple:
    """종목명 (코드) 패턴 → [[]] 링크 변환. (변환된 텍스트, 변환 수) 반환."""
    lines = text.splitlines(keepends=True)
    result = []
    total = 0

    for line in lines:
        for name in names_sorted:
            # 이미 [[stock_{name} 링크가 있으면 이 줄에서 skip
            if f"[[stock_{name}" in line:
                continue
            # 종목명 (6자리코드) 패턴
            pat = re.escape(name) + r"\s*\((\d{6})\)"
            new_line, n = re.subn(
                pat,
                lambda m, n=name: f"[[stock_{n}|{n} ({m.group(1)})]]",
                line,
            )
            if n:
                line = new_line
                total += n
        result.append(line)

    return "".join(result), total


def run():
    print(f"\n{'━'*52}")
    print(f"  link_fix.py — Obsidian 링크 표준화")
    print(f"{'━'*52}\n")

    for md in sorted(WIKI.rglob("*.md")):
        original = md.read_text(encoding="utf-8")
        updated, n = linkify(original)
        if updated != original:
            md.write_text(updated, encoding="utf-8")
            counts["files"] += 1
            counts["links"] += n
            rel = str(md.relative_to(ROOT)).replace("\\", "/")
            print(f"  [{n:>3}건] {rel}")

    print(f"\n{'━'*52}")
    print(f"  완료: {counts['files']}개 파일 / {counts['links']}개 링크 추가")
    print(f"{'━'*52}\n")


if __name__ == "__main__":
    run()
