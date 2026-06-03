from __future__ import annotations
from pathlib import Path
from scripts.channel_pipeline.models import WikiDecision

ROOT = Path(__file__).parent.parent.parent


def apply_decisions(
    decisions: list[WikiDecision],
    root: Path = ROOT,
    dry_run: bool = False,
) -> list[str]:
    """decisions 적용, 수정된(혹은 수정 예정) 파일 경로 목록 반환"""
    modified: list[str] = []
    for d in decisions:
        if d.action == "skip" or not d.wiki_file:
            continue
        path = root / d.wiki_file
        _ensure_file(path)
        content = path.read_text(encoding="utf-8")
        new_content = _apply_one(content, d)
        if new_content != content:
            if not dry_run:
                path.write_text(new_content, encoding="utf-8")
            modified.append(str(path))
    return modified


def _apply_one(content: str, d: WikiDecision) -> str:
    line = d.line
    if d.action == "flag" and d.conflict_note:
        line = f"{line} ⚠️ {d.conflict_note}"

    if d.section in content:
        # 섹션 헤더 바로 다음에 새 줄 삽입 (최상단)
        idx = content.index(d.section) + len(d.section)
        rest = content[idx:].lstrip("\n")
        return content[:idx] + "\n" + line + "\n" + rest
    else:
        # 섹션 없으면 파일 끝에 추가
        sep = "\n" if content.endswith("\n") else "\n\n"
        return content + sep + d.section + "\n" + line + "\n"


def _ensure_file(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        name = path.stem.replace("stock_", "")
        path.write_text(
            f"# {name}\n\n## 기본 정보\n(자동 생성)\n\n## 최신 이벤트\n",
            encoding="utf-8",
        )
