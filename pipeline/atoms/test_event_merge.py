import json
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.event_merge import merge_events


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    yield


def _ev(id_, src, content, date="2026-06-21"):
    import uuid
    from datetime import datetime
    conn = dbmod.get_conn()
    conn.execute(
        "INSERT INTO atoms (id,date,source_type,source_name,source_trust,raw_file,layer,"
        "sector,asset,asset_level,signal,event_type,magnitude,content_type,strength_score,"
        "content,relations,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (id_, date, "telegram", src, "B", "f.md", "L5", "기타", "시장", "market",
         "neutral", "event", "minor", "fact", 2, content, "[]", datetime.now().isoformat()))
    conn.commit(); conn.close()


def test_cross_channel_event_annotated():
    dbmod.init_db(); dbmod.migrate_db()
    _ev("a1", "대신시황", "미국-이란 MOU 체결")
    _ev("a2", "잠실개미", "미국 이란 MOU 체결!!")  # 같은 이벤트(정규화 동일)
    n = merge_events("2026-06-21")
    assert n == 2
    conn = dbmod.get_conn()
    r = conn.execute("SELECT mention_count, mention_channels FROM atoms WHERE id='a1'").fetchone()
    conn.close()
    assert r[0] == 2
    assert set(json.loads(r[1])) == {"대신시황", "잠실개미"}


def test_same_channel_no_merge():
    dbmod.init_db(); dbmod.migrate_db()
    _ev("b1", "대신시황", "코스피 상승")
    _ev("b2", "대신시황", "코스피 상승")  # 같은 채널 → 교차 아님
    n = merge_events("2026-06-21")
    assert n == 0  # 서로 다른 채널 아니므로 표시 안 함


def test_distinct_events_not_merged():
    dbmod.init_db(); dbmod.migrate_db()
    _ev("c1", "대신시황", "반도체 강세")
    _ev("c2", "잠실개미", "조선 약세")  # 다른 이벤트
    n = merge_events("2026-06-21")
    assert n == 0


def test_idempotent():
    dbmod.init_db(); dbmod.migrate_db()
    _ev("d1", "대신시황", "MOU 체결")
    _ev("d2", "뉴스봇", "MOU 체결")
    assert merge_events("2026-06-21") == 2
    assert merge_events("2026-06-21") == 2  # 재실행 동일(멱등)
