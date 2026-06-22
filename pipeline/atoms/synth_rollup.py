"""롤업: 종목 페이지 종합스토리 첫줄 → 섹터 인덱스. 설계 §4.4."""
import re
from pathlib import Path


def _first_story_line(md: str) -> str:
    m = re.search(r"## 종합 스토리\s*\n>\s*(.+)", md)
    return m.group(1).strip() if m else ""


def build_index(sector_dir: Path) -> str:
    rows = ["# 섹터 인덱스 (자동 롤업)", "", "| 종목 | 최신 한줄 |", "|------|----------|"]
    for f in sorted((sector_dir / "stock").glob("stock_*.md")):
        name = f.stem.replace("stock_", "")
        line = _first_story_line(f.read_text(encoding="utf-8"))
        if line:
            rows.append(f"| {name} | {line[:120]} |")
    return "\n".join(rows)
