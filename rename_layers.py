#!/usr/bin/env python3
"""
rename_layers.py — L1~L6 / 외부인사이트 index.md 를 {폴더명}index.md 로 일괄 변경
사용법: python rename_layers.py
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT  = Path(__file__).parent
WIKI  = ROOT / "wiki"
CANVAS = WIKI / "canvas"

# 대상 폴더 → 새 파일명
TARGETS = {
    "L1_글로벌유동성": "글로벌유동성index.md",
    "L2_미국시장":     "미국시장index.md",
    "L3_한국시장":     "한국시장index.md",
    "L4_국제정세":     "국제정세index.md",
    "L5_섹터":         "섹터index.md",
    "L6_수급":         "수급index.md",
    "외부인사이트":    "외부인사이트index.md",
}

# wiki/index.md (루트) → wiki/위키index.md
ROOT_INDEX = WIKI / "index.md"
ROOT_NEW   = WIKI / "위키index.md"

print(f"\n{'━'*52}")
print(f"  rename_layers.py — 레이어 index 파일명 변경")
print(f"{'━'*52}\n")

# ── 1단계: 파일 이름 변경 ─────────────────────────────────
print("[1/3] 파일 이름 변경...")
renamed = {}  # 폴더명 → 새 파일명 (stem)

for folder, new_name in sorted(TARGETS.items()):
    old_path = WIKI / folder / "index.md"
    new_path = WIKI / folder / new_name
    if old_path.exists():
        old_path.rename(new_path)
        renamed[folder] = new_name
        print(f"  {folder}/index.md  →  {new_name}")
    else:
        print(f"  ⚠️  {folder}/index.md 없음 — 건너뜀")

if ROOT_INDEX.exists():
    ROOT_INDEX.rename(ROOT_NEW)
    print(f"  index.md  →  위키index.md  (위키 루트)")

# ── 2단계: .md 파일 내 링크 업데이트 ───────────────────────
print("\n[2/3] .md 파일 링크 업데이트...")
md_count = 0

def update_links(text: str) -> str:
    # 레이어 폴더 index.md 링크
    for folder, new_name in renamed.items():
        stem = new_name.replace(".md", "")   # 예: 글로벌유동성index
        # [[폴더/index]] → [[폴더/stem]]
        text = re.sub(
            r'\[\[' + re.escape(folder) + r'/index(\|[^\]]+)?\]\]',
            lambda m, s=stem, f=folder: f"[[{f}/{s}{m.group(1) or ''}]]",
            text
        )
        # [[L1_글로벌유동성/index]] (full path) → [[L1_글로벌유동성/stem]]
        # 위와 동일하므로 이미 처리됨

        # wiki/L1_글로벌유동성/index.md (canvas용)
        text = text.replace(
            f"wiki/{folder}/index.md",
            f"wiki/{folder}/{new_name}"
        )
    # 루트 index 링크
    text = re.sub(r'\[\[index(\|[^\]]+)?\]\]',
                  lambda m: f"[[위키index{m.group(1) or ''}]]",
                  text)
    text = text.replace("wiki/index.md", "wiki/위키index.md")
    return text

for md in sorted(WIKI.rglob("*.md")):
    original = md.read_text(encoding="utf-8")
    updated  = update_links(original)
    if updated != original:
        md.write_text(updated, encoding="utf-8")
        md_count += 1
        print(f"  {md.relative_to(ROOT)}")

# ── 3단계: canvas 파일 경로 업데이트 ─────────────────────────
print("\n[3/3] Canvas 파일 경로 업데이트...")
canvas_count = 0

if CANVAS.exists():
    for canvas in sorted(CANVAS.glob("*.canvas")):
        original = canvas.read_text(encoding="utf-8")
        updated  = original
        for folder, new_name in renamed.items():
            updated = updated.replace(
                f"wiki/{folder}/index.md",
                f"wiki/{folder}/{new_name}"
            )
        updated = updated.replace("wiki/index.md", "wiki/위키index.md")
        if updated != original:
            canvas.write_text(updated, encoding="utf-8")
            canvas_count += 1
            print(f"  {canvas.name}")

if canvas_count == 0:
    print("  (변경 없음)")

print(f"\n{'━'*52}")
print(f"  완료: 파일 {len(renamed)+1}개 변경")
print(f"        .md {md_count}개 링크 업데이트")
print(f"        canvas {canvas_count}개 경로 업데이트")
print(f"{'━'*52}\n")
