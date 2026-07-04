import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom, get_conn


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _atom(**kw):
    base = dict(id="t1", date="2026-07-04", source_type="calendar",
                source_name="sector_calendar", source_trust="A", raw_file=None,
                layer="L5", sector="반도체", asset="삼성전자", asset_level="stock",
                signal="catalyst", event_type="event", magnitude="major",
                content_type="fact", strength_score=3,
                validity_type="date", validity_until="2026-07-15", is_active=1,
                content="본문", relations=[])
    base.update(kw)
    return base


def test_insert_atom_stores_event_date():
    insert_atom(_atom(event_date="2026-07-15"))
    conn = get_conn()
    row = conn.execute("SELECT event_date FROM atoms WHERE id=?", ("t1",)).fetchone()
    conn.close()
    assert row["event_date"] == "2026-07-15"


def test_insert_atom_without_event_date_is_null():
    insert_atom(_atom(id="t2"))
    conn = get_conn()
    row = conn.execute("SELECT event_date FROM atoms WHERE id=?", ("t2",)).fetchone()
    conn.close()
    assert row["event_date"] is None


def test_event_date_index_exists():
    conn = get_conn()
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_atoms_event_date'"
    ).fetchone()
    conn.close()
    assert idx is not None
