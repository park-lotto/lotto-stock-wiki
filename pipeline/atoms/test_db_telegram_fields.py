import json
import sqlite3
from pipeline.atoms.db import init_db, migrate_db, insert_atom, get_conn, DB_PATH


def _cleanup():
    """기존 DB 파일 삭제"""
    if DB_PATH.exists():
        DB_PATH.unlink()


def _base(**kw):
    a = {
        "id": "atom_tg_test_1", "date": "2026-06-19", "source_type": "telegram",
        "source_name": "하나반도체", "source_trust": "B", "raw_file": "x.md",
        "layer": "L5", "sector": "반도체", "asset": "SK하이닉스", "asset_level": "stock",
        "signal": "neutral", "event_type": "report", "magnitude": "minor",
        "content_type": "fact", "strength_score": 3, "validity_type": "permanent",
        "validity_until": None, "is_active": 1, "content": "테스트", "relations": [],
    }
    a.update(kw)
    return a


def test_migrate_is_idempotent():
    _cleanup()
    init_db(); migrate_db(); migrate_db()  # 두 번 호출해도 에러 없어야


def test_insert_without_new_fields_defaults():
    _cleanup()
    init_db(); migrate_db()
    insert_atom(_base(id="atom_tg_nofield"))
    conn = get_conn()
    row = conn.execute("SELECT mention_count, stance_key FROM atoms WHERE id='atom_tg_nofield'").fetchone()
    conn.close()
    assert row["mention_count"] == 1
    assert row["stance_key"] is None


def test_insert_with_new_fields():
    _cleanup()
    init_db(); migrate_db()
    insert_atom(_base(id="atom_tg_field", stance_key="태린이아빠|반도체",
                      mention_channels=["하나반도체", "대신시황"], mention_count=2, msg_ts="07:30"))
    conn = get_conn()
    row = conn.execute("SELECT * FROM atoms WHERE id='atom_tg_field'").fetchone()
    conn.close()
    assert row["mention_count"] == 2
    assert row["stance_key"] == "태린이아빠|반도체"
    assert json.loads(row["mention_channels"]) == ["하나반도체", "대신시황"]
    assert row["msg_ts"] == "07:30"
