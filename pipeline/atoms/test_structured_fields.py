import json
from pipeline.atoms.db import get_conn, init_db, insert_atom


def _base_atom(**kw):
    a = {
        "id": "test_sf_atom_1", "date": "2026-07-02", "source_type": "report",
        "source_name": "테스트", "source_trust": "A", "raw_file": "x.md",
        "layer": "L5", "sector": "기타", "asset": "삼성전자", "asset_level": "stock",
        "signal": "neutral", "event_type": "report", "magnitude": "minor",
        "content_type": "analysis", "strength_score": 1, "validity_type": "permanent",
        "validity_until": None, "is_active": 1, "content": "테스트 내용", "relations": [],
    }
    a.update(kw)
    return a


def test_insert_atom_stores_structured_fields_dict_as_json():
    init_db()
    insert_atom(_base_atom(id="test_sf_atom_dict",
                            structured_fields={"rating": "BUY", "tp_new": "100000"}))
    conn = get_conn()
    row = conn.execute("SELECT structured_fields FROM atoms WHERE id=?",
                        ("test_sf_atom_dict",)).fetchone()
    conn.close()
    assert row is not None
    assert json.loads(row["structured_fields"]) == {"rating": "BUY", "tp_new": "100000"}


def test_insert_atom_without_structured_fields_stores_null():
    init_db()
    insert_atom(_base_atom(id="test_sf_atom_none"))
    conn = get_conn()
    row = conn.execute("SELECT structured_fields FROM atoms WHERE id=?",
                        ("test_sf_atom_none",)).fetchone()
    conn.close()
    assert row is not None
    assert row["structured_fields"] is None
