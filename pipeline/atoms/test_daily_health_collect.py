# pipeline/atoms/test_daily_health_collect.py
import json
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.daily_health import collect_atom_counts, load_history, save_snapshot


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    yield


def test_collect_atom_counts(tmp_path):
    dbmod.init_db(); dbmod.migrate_db()
    import uuid
    from datetime import datetime
    conn = dbmod.get_conn()
    for st in ("telegram", "telegram", "news"):
        conn.execute(
            "INSERT INTO atoms (id,date,source_type,source_name,source_trust,raw_file,"
            "layer,sector,asset,asset_level,signal,event_type,magnitude,content_type,"
            "strength_score,content,relations,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), "2026-06-21", st, "x", 3, "f.md", "L5", "반도체", "a",
             "sector", "neutral", "report", "minor", "fact", 2, "c", "[]",
             datetime.now().isoformat()))
    conn.commit(); conn.close()
    counts = collect_atom_counts("2026-06-21")
    assert counts["telegram"] == 2
    assert counts["news"] == 1


def test_history_roundtrip(tmp_path):
    p = tmp_path / "hist.json"
    save_snapshot({"date": "2026-06-21", "atoms": {"telegram": 5}}, p)
    h = load_history(p)
    assert h["2026-06-21"]["atoms"]["telegram"] == 5


def test_load_history_missing(tmp_path):
    assert load_history(tmp_path / "none.json") == {}
