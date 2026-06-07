import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, query_atoms
from pipeline.atoms.ingest import (
    ingest_file,
    _guess_trust,
    _guess_source_type,
    _guess_layer,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def test_guess_trust_report_path():
    assert _guess_trust(Path("raw/wisereport/2026-06-07.md")) == "A"


def test_guess_trust_telegram_path():
    assert _guess_trust(Path("raw/telegram/2026-06-07_채널.md")) == "C"


def test_guess_trust_blog_path():
    assert _guess_trust(Path("raw/blog/2026-06-07_post.md")) == "D"


def test_guess_source_type_telegram():
    assert _guess_source_type(Path("raw/telegram/test.md")) == "telegram"


def test_guess_source_type_report():
    assert _guess_source_type(Path("raw/wisereport/test.md")) == "report"


def test_guess_layer_l5():
    assert _guess_layer(Path("raw/L5_섹터/반도체/test.md")) == "L5"


def test_guess_layer_default():
    assert _guess_layer(Path("raw/telegram/test.md")) == "L5"


@patch("pipeline.atoms.ingest.atomize_text")
def test_ingest_markdown_stores_atoms(mock_atomize, tmp_path, monkeypatch):
    test_file = tmp_path / "telegram" / "2026-06-07_신한.md"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("브로드컴 AI 가이던스 미달.", encoding="utf-8")

    mock_atomize.return_value = [{
        "id": "atom_test_001",
        "date": "2026-06-07",
        "source_type": "telegram",
        "source_name": "신한",
        "source_trust": "C",
        "raw_file": str(test_file),
        "layer": "L5",
        "sector": "반도체",
        "asset": "브로드컴",
        "asset_level": "stock",
        "signal": "bearish",
        "event_type": "earnings",
        "magnitude": "major",
        "content_type": "fact",
        "strength_score": 2,
        "validity_type": "permanent",
        "validity_until": None,
        "is_active": 1,
        "content": "브로드컴 AI 가이던스 미달.",
        "relations": [],
    }]

    count = ingest_file(str(test_file), "2026-06-07")
    assert count == 1
    results = query_atoms(sector="반도체", days=1)
    assert len(results) == 1
    assert results[0]["signal"] == "bearish"


def test_ingest_unknown_excel_returns_zero(tmp_path, capsys):
    test_file = tmp_path / "unknown_format.xlsx"
    test_file.write_bytes(b"PK\x03\x04")

    count = ingest_file(str(test_file), "2026-06-07")
    assert count == 0

    captured = capsys.readouterr()
    assert "인식 불가 Excel 파일:" in captured.out
    assert "unknown_format.xlsx" in captured.out


def test_ingest_nonexistent_file_returns_zero(tmp_path):
    nonexistent = tmp_path / "does_not_exist.md"

    count = ingest_file(str(nonexistent), "2026-06-07")
    assert count == 0
