import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
from pipeline.atoms.calendar_build import build_calendar_board


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    insert_atom(event_to_atom(
        {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
         "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True},
        sector="반도체", gen_date="2026-07-04"))
    yield


def test_board_written(tmp_path):
    path = build_calendar_board("2026-07-04", str(tmp_path))
    text = open(path, encoding="utf-8").read()
    assert "D-4" in text
    assert "삼성전자" in text
    assert "실적발표" in text
    assert "● 확정" in text
    assert path.endswith("캘린더_index.md")
