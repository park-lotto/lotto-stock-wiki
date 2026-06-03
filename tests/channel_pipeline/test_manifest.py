import os
import time
from pathlib import Path
from scripts.channel_pipeline.manifest import get_manifest, total_files


def test_empty_inbox(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.channel_pipeline.manifest.INBOX", tmp_path)
    manifest = get_manifest("2026-06-04")
    assert set(manifest.keys()) == {"telegram", "blog", "report", "yt"}
    assert all(len(v) == 0 for v in manifest.values())


def test_recent_file_included(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.channel_pipeline.manifest.INBOX", tmp_path)
    tg_dir = tmp_path / "telegram"
    tg_dir.mkdir()
    f = tg_dir / "20260604_태린이아빠.md"
    f.write_text("테스트", encoding="utf-8")
    manifest = get_manifest("2026-06-04")
    assert len(manifest["telegram"]) == 1
    assert str(f) in manifest["telegram"]


def test_old_file_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.channel_pipeline.manifest.INBOX", tmp_path)
    tg_dir = tmp_path / "telegram"
    tg_dir.mkdir()
    f = tg_dir / "20260101_old.md"
    f.write_text("오래된 파일", encoding="utf-8")
    old_time = time.time() - (8 * 24 * 3600)
    os.utime(f, (old_time, old_time))
    manifest = get_manifest("2026-06-04")
    assert len(manifest["telegram"]) == 0


def test_total_files():
    manifest = {"telegram": ["a", "b"], "blog": ["c"], "report": [], "yt": []}
    assert total_files(manifest) == 3
