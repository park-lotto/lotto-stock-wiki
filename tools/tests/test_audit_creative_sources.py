import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from tools.audit_creative_sources import SOURCES, inspect_database, inspect_source


def test_audit_reports_missing_duplicate_and_escaping_files(tmp_path):
    registry = tmp_path / SOURCES[0][1]
    root = tmp_path / SOURCES[0][2]
    root.mkdir(parents=True)
    (root / "one.ttf").write_bytes(b"fixture")
    (root / "two.ttf").write_bytes(b"fixture")
    (root / "unused.ttf").write_bytes(b"unused")
    entries = [{"file": name} for name in ["one.ttf", "two.ttf", "missing.ttf", "../outside.ttf"]]
    registry.write_text(json.dumps(entries), encoding="utf-8")
    report = inspect_source(tmp_path, SOURCES[0], False, None)
    assert report["counts"] == {"present": 2, "missing_file": 1, "outside_asset_root": 1}
    assert report["duplicate_files"] == [["one.ttf", "two.ttf"]]
    assert report["unregistered_files"] == ["unused.ttf"]
    assert report["physical_file_count"] == 3
    assert all(item["rights_status"] == "not_reviewed" for item in report["items"])


def test_database_audit_never_creates_or_changes_database(tmp_path):
    missing = tmp_path / "missing.db"
    assert inspect_database(missing)["status"] == "missing_database"
    assert not missing.exists()
    database = tmp_path / "reference.db"
    conn = sqlite3.connect(database)
    conn.execute("CREATE TABLE scene_assets(id INTEGER, private_text TEXT)")
    conn.execute("INSERT INTO scene_assets VALUES (1, 'private customer material')")
    conn.commit()
    conn.close()
    before = database.read_bytes()
    result = inspect_database(database)
    assert result["tables"]["scene_assets"] == 1
    assert result["tables"]["spine"] is None
    assert "private customer material" not in json.dumps(result)
    assert database.read_bytes() == before


def test_cli_refuses_existing_output_before_overwriting(tmp_path):
    (tmp_path / "shopping_shorts").mkdir()
    output = tmp_path / "keep.json"
    output.write_text("keep", encoding="utf-8")
    script = Path(__file__).parents[1] / "audit_creative_sources.py"
    result = subprocess.run([sys.executable, str(script), "--repo", str(tmp_path),
                             "--output", str(output)], capture_output=True)
    assert result.returncode != 0
    assert output.read_text(encoding="utf-8") == "keep"
