#!/usr/bin/env python3
"""
merge_table.py — 각 섹터의 테이블.md 내용을 {섹터}index.md에 병합 후 삭제
사용법: python merge_table.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
WIKI = ROOT / "wiki"
L5   = WIKI / "L5_섹터"

print(f"\n{'━'*52}")
print(f"  merge_table.py — 테이블.md → {'{섹터}'}index.md 병합")
print(f"{'━'*52}\n")

# ── 1단계: 각 섹터별 병합 ─────────────────────────────────
print("[1/2] 병합 작업...")
merged_count = 0
skipped_count = 0

for sector_dir in sorted(L5.iterdir()):
    if not sector_dir.is_dir():
        continue

    table_path = sector_dir / "테이블.md"
    index_name = f"{sector_dir.name}index.md"
    index_path = sector_dir / index_name

    if not table_path.exists():
        continue
    if not index_path.exists():
        print(f"  ⚠️  {sector_dir.name}: index 없음 — 건너뜀")
        skipped_count += 1
        continue

    table_text = table_path.read_text(encoding="utf-8")
    index_text = index_path.read_text(encoding="utf-8")

    # 테이블.md에서 H1 헤더·preamble·관련 페이지 섹션 제거
    lines = table_text.splitlines(keepends=True)
    body_lines = []
    skip_related = False
    for i, line in enumerate(lines):
        if i == 0 and line.startswith("# "):
            continue  # H1 제목 제거
        if line.strip().startswith("## 관련 페이지"):
            skip_related = True
        if skip_related:
            continue
        body_lines.append(line)

    table_body = "".join(body_lines).strip()
    if not table_body:
        print(f"  ⚠️  {sector_dir.name}: 테이블 내용 없음 — 건너뜀")
        skipped_count += 1
        continue

    # index.md의 ## 관련 페이지 바로 앞에 삽입
    RELATED_MARKER = "\n## 관련 페이지"
    if RELATED_MARKER in index_text:
        insert_pos = index_text.index(RELATED_MARKER)
        new_index = (
            index_text[:insert_pos].rstrip()
            + "\n\n---\n\n## 📋 서브섹터 매핑\n\n"
            + table_body
            + "\n\n"
            + index_text[insert_pos:].lstrip()
        )
    else:
        new_index = (
            index_text.rstrip()
            + "\n\n---\n\n## 📋 서브섹터 매핑\n\n"
            + table_body
            + "\n"
        )

    index_path.write_text(new_index, encoding="utf-8")
    table_path.unlink()
    merged_count += 1
    print(f"  ✅  {sector_dir.name}: 테이블.md → {index_name}")

# ── 2단계: 전체 .md에서 테이블 링크 업데이트 ────────────────
print(f"\n[2/2] 링크 업데이트...")
link_count = 0
sector_names = [d.name for d in L5.iterdir() if d.is_dir()]

for md in sorted(WIKI.rglob("*.md")):
    text = md.read_text(encoding="utf-8")
    if "테이블" not in text:
        continue
    updated = text
    for sec in sector_names:
        idx_stem = f"{sec}index"
        # [[{섹터}/테이블]] 형태
        updated = updated.replace(f"[[{sec}/테이블]]",           f"[[{sec}/{idx_stem}]]")
        updated = updated.replace(f"[[{sec}/테이블|",            f"[[{sec}/{idx_stem}|")
        # [[L5_섹터/{섹터}/테이블]] 형태
        updated = updated.replace(f"[[L5_섹터/{sec}/테이블]]",   f"[[L5_섹터/{sec}/{idx_stem}]]")
        updated = updated.replace(f"[[L5_섹터/{sec}/테이블|",    f"[[L5_섹터/{sec}/{idx_stem}|")
        # sector_반도체.md → 테이블 참조 형태 (대시보드 주석 등)
        updated = updated.replace(f"wiki/L5_섹터/{sec}/테이블.md",
                                  f"wiki/L5_섹터/{sec}/{idx_stem}.md")
    if updated != text:
        md.write_text(updated, encoding="utf-8")
        link_count += 1
        print(f"  {md.relative_to(ROOT)}")

print(f"\n{'━'*52}")
print(f"  완료: {merged_count}개 섹터 병합")
print(f"        {skipped_count}개 건너뜀")
print(f"        {link_count}개 파일 링크 업데이트")
print(f"{'━'*52}\n")
