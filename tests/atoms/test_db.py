import pytest
from pathlib import Path
from datetime import datetime, date, timedelta
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, insert_atom, query_atoms, expire_atoms, get_atom_count

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_atoms.db")
    init_db()

def _make_atom(overrides=None):
    base = {
        "id": "atom_test_001",
        "date": date.today().isoformat(),
        "source_type": "telegram",
        "source_name": "신한리서치",
        "source_trust": "B",
        "raw_file": "raw/telegram/test.md",
        "layer": "L5",
        "sector": "반도체",
        "asset": "브로드컴",
        "asset_level": "stock",
        "signal": "bearish",
        "event_type": "earnings",
        "magnitude": "major",
        "content_type": "fact",
        "strength_score": 4,
        "validity_type": "permanent",
        "validity_until": None,
        "is_active": 1,
        "content": "브로드컴 AI 가이던스 -11.8% 미달. 시장 예상 하회.",
        "relations": [],
    }
    if overrides:
        base.update(overrides)
    return base

def test_insert_and_retrieve():
    atom = _make_atom()
    insert_atom(atom)
    results = query_atoms(sector="반도체", days=1)
    assert len(results) == 1
    assert results[0]["asset"] == "브로드컴"
    assert results[0]["signal"] == "bearish"

def test_content_preserved_exactly():
    original = "브로드컴 AI 가이던스 -11.8% 미달. 절대 요약 금지."
    insert_atom(_make_atom({"content": original}))
    results = query_atoms(days=1)
    assert results[0]["content"] == original

def test_query_by_signal():
    insert_atom(_make_atom({"id": "atom_001", "signal": "bullish"}))
    insert_atom(_make_atom({"id": "atom_002", "signal": "bearish"}))
    bullish = query_atoms(signal="bullish", days=1)
    assert len(bullish) == 1
    assert bullish[0]["signal"] == "bullish"

def test_query_by_asset():
    insert_atom(_make_atom({"asset": "SK하이닉스"}))
    results = query_atoms(asset="SK하이닉스", days=1)
    assert len(results) == 1

def test_expire_atoms_by_date():
    expired_date = (date.today() - timedelta(days=3)).isoformat()
    atom = _make_atom({
        "id": "atom_expired",
        "date": "2026-01-01",
        "validity_type": "date",
        "validity_until": expired_date,
    })
    insert_atom(atom)
    count = expire_atoms()
    assert count >= 1
    active = query_atoms(days=365, active_only=True)
    assert all(r["id"] != "atom_expired" for r in active)

def test_permanent_atom_not_expired():
    insert_atom(_make_atom({"validity_type": "permanent", "validity_until": None}))
    expire_atoms()
    results = query_atoms(days=1)
    assert len(results) == 1

def test_get_atom_count():
    insert_atom(_make_atom({"id": "atom_a"}))
    insert_atom(_make_atom({"id": "atom_b"}))
    assert get_atom_count() == 2

def test_relations_deserialized_as_list():
    atom = _make_atom({"relations": [{"type": "confirms", "target_id": "atom_002"}]})
    insert_atom(atom)
    results = query_atoms(days=1)
    assert isinstance(results[0]["relations"], list)
    assert results[0]["relations"][0]["type"] == "confirms"
