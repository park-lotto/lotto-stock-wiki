import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
from pipeline.atoms.calendar_build import select_future_events


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    _seed()
    yield


def _seed():
    evs = [
        ({"date": "2026-07-08", "company": "삼성전자", "event": "2Q 실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}, "반도체"),
        ({"date": "2026-07-25", "company": "HD현대중공업", "event": "2Q 실적",
          "type": "실적발표", "importance": "[MID]", "desc": "", "confirmed": True}, "조선"),
        ({"date": "2026-06-30", "company": "삼성전자", "event": "지난 이벤트",
          "type": "실적발표", "importance": "[LOW]", "desc": "", "confirmed": True}, "반도체"),
    ]
    for ev, sec in evs:
        insert_atom(event_to_atom(ev, sector=sec, gen_date="2026-07-04"))


def test_only_future_sorted():
    out = select_future_events("2026-07-04")
    assert [e["event_date"] for e in out] == ["2026-07-08", "2026-07-25"]  # 06-30 제외


def test_dday_computed():
    out = select_future_events("2026-07-04")
    assert out[0]["dday"] == 4
    assert out[0]["structured_fields"]["event_kind"] == "실적발표"


def test_watchlist_filter():
    out = select_future_events("2026-07-04", watchlist=["삼성전자"])
    assert [e["asset"] for e in out] == ["삼성전자"]


def test_sector_filter():
    out = select_future_events("2026-07-04", sector="조선")
    assert [e["asset"] for e in out] == ["HD현대중공업"]
