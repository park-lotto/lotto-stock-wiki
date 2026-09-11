#!/usr/bin/env python3
"""수집된 폰트 파일을 실제로 열어 내부 이름·한글 지원·중복을 검사한다."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "font_collection"
EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def names(font: TTFont, name_id: int) -> list[str]:
    values = []
    for record in font["name"].names:
        if record.nameID != name_id:
            continue
        try:
            value = record.toUnicode().strip()
        except Exception:
            continue
        if value and value not in values:
            values.append(value)
    return values


def inspect(path: Path) -> dict:
    base = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }
    try:
        font = TTFont(path, lazy=True, fontNumber=0)
        cmap = set()
        for table in font["cmap"].tables:
            cmap.update(table.cmap)
        hangul_syllables = sum(0xAC00 <= cp <= 0xD7A3 for cp in cmap)
        hangul_jamo = sum(
            0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F or 0xA960 <= cp <= 0xA97F
            for cp in cmap
        )
        base.update(
            {
                "valid": True,
                "families": names(font, 1),
                "subfamilies": names(font, 2),
                "full_names": names(font, 4),
                "postscript_names": names(font, 6),
                "glyphs": len(cmap),
                "hangul_syllables": hangul_syllables,
                "hangul_jamo": hangul_jamo,
                "has_korean": hangul_syllables > 0 or hangul_jamo >= 20,
            }
        )
        font.close()
    except Exception as exc:
        base.update({"valid": False, "error": f"{type(exc).__name__}: {exc}"})
    return base


def main() -> int:
    paths = sorted(
        p
        for p in (COLLECTION / "files").rglob("*")
        if p.suffix.lower() in EXTENSIONS
        and not p.name.startswith("._")
        and "__MACOSX" not in p.parts
    )
    print(f"[audit] files={len(paths)}", flush=True)
    rows = []
    for index, path in enumerate(paths, 1):
        rows.append(inspect(path))
        if index % 50 == 0 or index == len(paths):
            print(f"[audit] {index}/{len(paths)}", flush=True)
    by_hash = defaultdict(list)
    for row in rows:
        by_hash[row["sha256"]].append(row["path"])
    duplicates = [paths for paths in by_hash.values() if len(paths) > 1]
    source_of = lambda row: Path(row["path"]).parts[2]
    report = {
        "files": len(rows),
        "valid": sum(x.get("valid", False) for x in rows),
        "invalid": sum(not x.get("valid", False) for x in rows),
        "with_korean": sum(x.get("has_korean", False) for x in rows),
        "without_korean": sum(x.get("valid") and not x.get("has_korean") for x in rows),
        "bytes": sum(x["bytes"] for x in rows),
        "duplicate_groups": len(duplicates),
        "duplicate_extra_files": sum(len(x) - 1 for x in duplicates),
        "extensions": dict(Counter(Path(x["path"]).suffix.lower() for x in rows)),
        "files_by_source": dict(Counter(source_of(x) for x in rows)),
        "korean_files_by_source": dict(
            Counter(source_of(x) for x in rows if x.get("has_korean"))
        ),
    }
    out = COLLECTION / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "files.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "duplicates.json").write_text(
        json.dumps(duplicates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["invalid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
