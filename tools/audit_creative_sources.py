"""Read-only technical inventory of the current creative source files.

The output is an inspection report, never an approval or a new asset registry.
No application modules are imported and no databases are created or updated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess


SOURCES = (
    ("fonts", "shopping_shorts/static/fonts.json", "shopping_shorts/static/fonts", "file", None),
    ("motion", "shopping_shorts/assets/motion/manifest.json", "shopping_shorts/assets/motion", "file", "assets"),
    ("voices", "shopping_shorts/assets/voice_presets.json", "shopping_shorts/assets/voice_samples", "sample_file", None),
)
TABLES = ("scene_assets", "spine", "pattern_item", "pattern_source", "script_usage")
SAMPLE = "숏템메이커 놀라운 생활 아이디어 0123456789 ABC!?"


def fingerprint(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_font(path: Path) -> dict:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return {"status": "not_checked", "reason": "fontTools_unavailable"}
    try:
        with TTFont(path, lazy=True) as font:
            cmap = font.getBestCmap() or {}
            return {
                "status": "parsed",
                "hangul_syllables": sum(0xAC00 <= cp <= 0xD7A3 for cp in cmap),
                "sample": SAMPLE,
                "missing_sample_glyphs": sorted({char for char in SAMPLE if not char.isspace() and ord(char) not in cmap}),
                "weight": getattr(font.get("OS/2"), "usWeightClass", None),
                "embedding_fs_type": getattr(font.get("OS/2"), "fsType", None),
                "note": "Technical metadata only; fsType is not a license decision.",
            }
    except Exception as exc:
        return {"status": "error", "reason": type(exc).__name__}


def inspect_media(path: Path, ffprobe: str | None) -> dict:
    if not ffprobe:
        return {"status": "not_checked", "reason": "ffprobe_unavailable"}
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,pix_fmt,width,height,sample_rate,channels",
             "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        if result.returncode:
            return {"status": "error", "reason": "ffprobe_failed", "returncode": result.returncode}
        return {"status": "parsed", **json.loads(result.stdout)}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"status": "error", "reason": type(exc).__name__}


def inspect_source(repo: Path, spec: tuple, technical: bool, ffprobe: str | None) -> dict:
    domain, registry_rel, asset_rel, field, container = spec
    registry = repo / registry_rel
    report = {"domain": domain, "registry": registry_rel, "scope": "local_files", "items": []}
    if not registry.is_file():
        return {**report, "status": "missing_registry"}
    try:
        entries = json.loads(registry.read_text(encoding="utf-8-sig"))
        if container:
            entries = entries[container]
        if not isinstance(entries, list):
            raise ValueError("registry must contain a list")
    except (ValueError, KeyError, TypeError) as exc:
        return {**report, "status": "invalid_registry", "error": type(exc).__name__}
    root = (repo / asset_rel).resolve()
    report.update(status="inspected", registry_sha256=fingerprint(registry), registered_count=len(entries))
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            report["items"].append({"index": index, "status": "invalid_record"})
            continue
        filename = entry.get(field)
        item = {"index": index, "legacy_id": entry.get("id") or entry.get("preset_id") or entry.get("css"),
                "name": entry.get("name"), "file": filename, "rights_status": "not_reviewed"}
        if not isinstance(filename, str) or not filename.strip():
            report["items"].append({**item, "status": "missing_reference"})
            continue
        path = (root / filename).resolve()
        if not path.is_relative_to(root):
            report["items"].append({**item, "status": "outside_asset_root"})
            continue
        if not path.is_file():
            report["items"].append({**item, "status": "missing_file"})
            continue
        item.update(status="present", bytes=path.stat().st_size, sha256=fingerprint(path))
        if technical:
            item["technical"] = inspect_font(path) if domain == "fonts" else inspect_media(path, ffprobe)
        report["items"].append(item)
    report["counts"] = dict(Counter(item["status"] for item in report["items"]))
    extensions = {"fonts": {".ttf", ".otf", ".woff", ".woff2"},
                  "motion": {".mov", ".webm", ".mp4"},
                  "voices": {".mp3", ".wav", ".m4a", ".ogg"}}[domain]
    registered = {(root / item["file"]).resolve() for item in report["items"]
                  if item.get("status") == "present"}
    disk_files = sorted(path for path in root.rglob("*")
                        if path.is_file() and path.suffix.lower() in extensions
                        and path.resolve().is_relative_to(root)) if root.is_dir() else []
    report["physical_file_count"] = len(disk_files)
    report["unregistered_files"] = [path.relative_to(root).as_posix() for path in disk_files
                                    if path.resolve() not in registered]
    hashes = defaultdict(list)
    for item in report["items"]:
        if item.get("sha256"):
            hashes[item["sha256"]].append(item["file"])
    report["duplicate_files"] = [sorted(set(paths)) for paths in hashes.values() if len(set(paths)) > 1]
    return report


def inspect_database(path: Path | None) -> dict:
    if path is None:
        return {"status": "not_requested", "scope": "local_database"}
    if not path.is_file():
        return {"status": "missing_database", "scope": "local_database"}
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
            conn.execute("PRAGMA query_only=ON")
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                      if table in names else None for table in TABLES}
        return {"status": "inspected", "scope": "local_database", "tables": counts,
                "note": "Counts only; no customer rows exported. This is not server inventory."}
    except sqlite3.Error as exc:
        return {"status": "error", "scope": "local_database", "reason": type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--technical", action="store_true", help="Parse font glyphs and probe audio/video.")
    parser.add_argument("--output", type=Path, help="Write a new JSON report; existing files are never overwritten.")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / "shopping_shorts").is_dir():
        parser.error("--repo must contain shopping_shorts")
    if args.output and args.output.exists():
        parser.error("--output already exists; choose a new report filename")
    ffprobe = shutil.which("ffprobe")
    report = {
        "schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "read_only_technical_inventory", "approval_granted": False,
        "technical_requested": args.technical, "ffprobe_available": bool(ffprobe),
        "sources": [inspect_source(repo, spec, args.technical, ffprobe) for spec in SOURCES],
        "database": inspect_database(args.db),
        "limitations": ["License and visual/editorial approval are not inferred from parse success.",
                        "Code-generated and customer-only recipes are inspected through the catalog adapters.",
                        "ffprobe metadata is not a full playback or listening test."],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
        print(json.dumps({"report": str(args.output), "sources": [
            {"domain": s["domain"], "status": s["status"], "counts": s.get("counts", {})}
            for s in report["sources"]], "database": report["database"]}, ensure_ascii=False))
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
