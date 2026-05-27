#!/usr/bin/env python3
"""
rename_index.py — 각 섹터 index.md → {섹터}index.md 일괄 변경
사용법: python rename_index.py
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT  = Path(__file__).parent
WIKI  = ROOT / "wiki"
L5    = WIKI / "L5_섹터"
CANVAS = WIKI / "canvas"

# 섹터명 → 새 파일명 매핑
RENAMES = {}
for sector_dir in L5.iterdir():
    if sector_dir.is_dir():
        old = sector_dir / "index.md"
        if old.exists():
            new_name = f"{sector_dir.name}index.md"
            RENAMES[sector_dir.name] = new_name  # 섹터명 → 새 파일명

print(f"\n{'━'*52}")
print(f"  rename_index.py — 섹터 index 파일명 변경")
print(f"{'━'*52}\n")

# ── 1단계: 파일 이름 변경 ────────────────────────────────
print("[1/3] 파일 이름 변경...")
for sector, new_name in sorted(RENAMES.items()):
    old_path = L5 / sector / "index.md"
    new_path = L5 / sector / new_name
    old_path.rename(new_path)
    print(f"  {sector}/index.md  →  {new_name}")

# ── 2단계: .md 파일 내 링크 업데이트 ────────────────────
print("\n[2/3] .md 파일 링크 업데이트...")
md_count = 0

def update_md_links(text: str) -> str:
    for sector, new_name in RENAMES.items():
        stem = new_name.replace(".md", "")   # 예: 반도체index
        # [[반도체/index]] → [[반도체/반도체index]]
        text = re.sub(
            r'\[\[' + re.escape(sector) + r'/index(\|[^\]]+)?\]\]',
            lambda m: f"[[{sector}/{stem}{m.group(1) or ''}]]",
            text
        )
        # [[L5_섹터/반도체/index]] → [[L5_섹터/반도체/반도체index]]
        text = re.sub(
            r'\[\[L5_섹터/' + re.escape(sector) + r'/index(\|[^\]]+)?\]\]',
            lambda m: f"[[L5_섹터/{sector}/{stem}{m.group(1) or ''}]]",
            text
        )
    return text

for md in sorted(WIKI.rglob("*.md")):
    original = md.read_text(encoding="utf-8")
    updated  = update_md_links(original)
    if updated != original:
        md.write_text(updated, encoding="utf-8")
        md_count += 1
        print(f"  {md.relative_to(ROOT)}")

# ── 3단계: .canvas 파일 내 경로 업데이트 ─────────────────
print("\n[3/3] Canvas 파일 경로 업데이트...")
canvas_count = 0

for canvas in sorted(CANVAS.glob("*.canvas")):
    original = canvas.read_text(encoding="utf-8")
    updated  = original
    for sector, new_name in RENAMES.items():
        # "wiki/L5_섹터/반도체/index.md" → "wiki/L5_섹터/반도체/반도체index.md"
        updated = updated.replace(
            f"wiki/L5_섹터/{sector}/index.md",
            f"wiki/L5_섹터/{sector}/{new_name}"
        )
    if updated != original:
        canvas.write_text(updated, encoding="utf-8")
        canvas_count += 1
        print(f"  {canvas.name}")

print(f"\n{'━'*52}")
print(f"  완료: 파일 {len(RENAMES)}개 변경")
print(f"        .md {md_count}개 링크 업데이트")
print(f"        canvas {canvas_count}개 경로 업데이트")
print(f"{'━'*52}\n")
