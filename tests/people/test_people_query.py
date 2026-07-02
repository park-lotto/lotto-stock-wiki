import pytest
from datetime import date
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, insert_atom
from pipeline.people.people_query import atoms_for


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_atoms.db")
    init_db()


def _atom(overrides=None):
    base = {
        "id": "a1", "date": date.today().isoformat(),
        "source_type": "telegram", "source_name": "태린이아빠 주식투자",
        "source_trust": "B", "raw_file": "raw/x.md",
        "layer": "L6", "sector": "조선", "asset": "HD현대중공업", "asset_level": "stock",
        "signal": "bullish", "event_type": "news", "magnitude": 1, "content_type": "stance", "strength_score": 3,
        "validity_type": "permanent", "validity_until": None,
        "is_active": 1, "content": "조선 비중 확대 유지.", "relations": [],
    }
    if overrides:
        base.update(overrides)
    return base


def test_atoms_for_returns_only_person_sources():
    insert_atom(_atom({"id": "mine1"}))
    insert_atom(_atom({"id": "mine2", "source_name": "태린이아빠"}))  # 유튜브
    insert_atom(_atom({"id": "other", "source_name": "신한리서치"}))
    got = atoms_for("태린이아빠")
    ids = {a["id"] for a in got}
    assert ids == {"mine1", "mine2"}


def test_atoms_for_filters_content_type():
    insert_atom(_atom({"id": "s1", "content_type": "stance"}))
    insert_atom(_atom({"id": "m1", "content_type": "method"}))
    got = atoms_for("태린이아빠", content_type="method")
    assert [a["id"] for a in got] == ["m1"]


def test_atoms_for_active_only():
    insert_atom(_atom({"id": "act", "is_active": 1}))
    insert_atom(_atom({"id": "dead", "is_active": 0}))
    ids = {a["id"] for a in atoms_for("태린이아빠")}
    assert ids == {"act"}


def test_atoms_for_ordered_newest_first():
    insert_atom(_atom({"id": "old", "date": "2026-06-01"}))
    insert_atom(_atom({"id": "new", "date": "2026-06-30"}))
    got = atoms_for("태린이아빠", days=3650)
    assert got[0]["id"] == "new"


def test_atoms_for_stance_only_filters_by_stance_key():
    insert_atom(_atom({"id": "s1", "stance_key": "태린이아빠 주식투자|반도체"}))
    insert_atom(_atom({"id": "s2", "stance_key": None}))
    got = atoms_for("태린이아빠", stance_only=True)
    assert [a["id"] for a in got] == ["s1"]
