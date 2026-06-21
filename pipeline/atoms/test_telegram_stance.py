import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, migrate_db, insert_atom, get_conn
from pipeline.atoms.telegram_stance import deactivate_prior_stance


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    """모든 테스트를 임시 DB로 격리 — 운영 atoms.db를 절대 건드리지 않음"""
    test_db_path = tmp_path / "test_atoms.db"
    monkeypatch.setattr(dbmod, "DB_PATH", test_db_path)
    yield test_db_path


def _stance(id_, key, date):
    return {
        "id": id_, "date": date, "source_type": "telegram", "source_name": "태린이아빠 주식투자",
        "source_trust": "B", "raw_file": "x.md", "layer": "L5", "sector": "반도체",
        "asset": "반도체", "asset_level": "stance", "signal": "bullish",
        "event_type": "report", "magnitude": "minor", "content_type": "opinion",
        "strength_score": 3, "validity_type": "permanent", "validity_until": None,
        "is_active": 1, "content": "긍정", "relations": [],
        "stance_key": key, "mention_count": 1,
    }


def test_prior_stance_deactivated():
    init_db(); migrate_db()
    key = "태린이아빠 주식투자|반도체"
    insert_atom(_stance("atom_st_old", key, "2026-06-19"))
    # 신규 스탠스 도착 → 옛것 비활성화
    n = deactivate_prior_stance(key, keep_id="atom_st_new")
    insert_atom(_stance("atom_st_new", key, "2026-06-25"))
    conn = get_conn()
    old = conn.execute("SELECT is_active FROM atoms WHERE id='atom_st_old'").fetchone()
    new = conn.execute("SELECT is_active FROM atoms WHERE id='atom_st_new'").fetchone()
    conn.close()
    assert old["is_active"] == 0   # 과거 보존하되 비활성
    assert new["is_active"] == 1   # 현재만 활성
    assert n >= 1


def test_no_deactivation_when_no_stance_key():
    init_db(); migrate_db()
    insert_atom(_stance("atom_st_1", "key1|반도체", "2026-06-19"))
    n = deactivate_prior_stance("", keep_id="atom_st_new")
    assert n == 0


def test_keeps_specified_atom_active():
    init_db(); migrate_db()
    key = "채널1|대상1"
    insert_atom(_stance("atom_1", key, "2026-06-19"))
    insert_atom(_stance("atom_2", key, "2026-06-20"))
    insert_atom(_stance("atom_3", key, "2026-06-21"))

    # atom_2를 keep_id로 지정 → atom_1, atom_3만 비활성화
    n = deactivate_prior_stance(key, keep_id="atom_2")

    conn = get_conn()
    a1 = conn.execute("SELECT is_active FROM atoms WHERE id='atom_1'").fetchone()
    a2 = conn.execute("SELECT is_active FROM atoms WHERE id='atom_2'").fetchone()
    a3 = conn.execute("SELECT is_active FROM atoms WHERE id='atom_3'").fetchone()
    conn.close()

    assert a1["is_active"] == 0
    assert a2["is_active"] == 1  # keep_id는 그대로 활성
    assert a3["is_active"] == 0
    assert n == 2
