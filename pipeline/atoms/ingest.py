"""
ingest.py — 단일 파일을 원자화하여 Atom DB에 저장.

사용법:
    python -m pipeline.atoms.ingest <파일경로> [날짜 YYYY-MM-DD]

예시:
    python -m pipeline.atoms.ingest raw/telegram/2026-06-07_신한.md 2026-06-07
    python -m pipeline.atoms.ingest raw/supply/oscillator.xlsx 2026-06-07
"""
import sys
from pathlib import Path
from datetime import datetime

from .db import init_db, insert_atom
from .atomizer import atomize_text
from .excel_converter import oscillator_to_atoms, consensus_to_atoms, oscillator_json_to_atoms
from .taxonomy import SOURCE_TRUST_BY_PATH

_EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
_TEXT_SUFFIXES = {".md", ".txt"}
_JSON_SUFFIXES = {".json"}


def ingest_file(file_path: str, date: str = None, source_trust: str = None) -> int:
    path = Path(file_path)
    date = date or datetime.now().strftime("%Y-%m-%d")

    if not path.exists():
        return 0

    if path.suffix in _EXCEL_SUFFIXES:
        return _ingest_excel(path, date)

    if path.suffix in _TEXT_SUFFIXES:
        return _ingest_text(path, date, source_trust)

    if path.suffix in _JSON_SUFFIXES:
        return _ingest_json(path, date)

    return 0


def _ingest_excel(path: Path, date: str) -> int:
    name = path.stem.lower()
    atoms: list[dict] = []

    if "오실레이터" in name or "oscillator" in name or "수급" in name:
        atoms = oscillator_to_atoms(str(path), date)
    elif "컨센" in name or "consensus" in name or "이익" in name:
        atoms = consensus_to_atoms(str(path), date)
    else:
        print(f"[WARN] 인식 불가 Excel 파일: {path.name} (0개 저장)")
        return 0

    for atom in atoms:
        insert_atom(atom)
    return len(atoms)


def _ingest_json(path: Path, date: str) -> int:
    name = path.stem.lower()
    if "oscillator" in name or "오실레이터" in name or "scan" in name:
        atoms = oscillator_json_to_atoms(str(path), date)
    else:
        print(f"[WARN] 인식 불가 JSON 파일: {path.name} (0개 저장)")
        return 0
    for atom in atoms:
        insert_atom(atom)
    return len(atoms)


def _ingest_text(path: Path, date: str, force_trust: str = None) -> int:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if not text.strip():
        return 0

    source_name = _extract_source_name(path)
    trust = force_trust or _guess_trust(path)
    source_type = _guess_source_type(path)
    layer = _guess_layer(path)

    atoms = atomize_text(
        text=text,
        source_type=source_type,
        source_name=source_name,
        source_trust=trust,
        raw_file=str(path),
        date=date,
        layer=layer,
    )
    for atom in atoms:
        insert_atom(atom)
    return len(atoms)


def _extract_source_name(path: Path) -> str:
    stem = path.stem
    parts = stem.split("_")
    return parts[-1] if len(parts) > 1 else stem


def _guess_trust(path: Path) -> str:
    name = str(path).lower().replace("\\", "/")
    for key, trust in SOURCE_TRUST_BY_PATH.items():
        if key in name:
            return trust
    return "D"


def _guess_source_type(path: Path) -> str:
    name = str(path).lower().replace("\\", "/")
    if "telegram" in name:
        return "telegram"
    if "report" in name or "wisereport" in name:
        return "report"
    if "news" in name:
        return "news"
    if "blog" in name:
        return "blog"
    if "market" in name:
        return "news"
    return "unknown"


def _guess_layer(path: Path) -> str:
    name = str(path)
    for layer in ["L1", "L2", "L3", "L4", "L5", "L6"]:
        if layer in name:
            return layer
    return "L5"


if __name__ == "__main__":
    init_db()
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.atoms.ingest <file_path> [date]")
        sys.exit(1)
    file_path = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else None
    count = ingest_file(file_path, date)
    print(f"[OK] {count}개 원자 저장 완료")
