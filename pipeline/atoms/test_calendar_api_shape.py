import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
from pipeline.atoms.calendar_build import select_future_events, to_api_dict


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    for ev, sec in [
        ({"date": "2026-07-08", "company": "삼성전자", "event": "2Q 실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}, "반도체"),
        ({"date": "2026-08-20", "company": "HD현대중공업", "event": "먼 이벤트",
          "type": "실적발표", "importance": "[MID]", "desc": "", "confirmed": True}, "조선"),
    ]:
        insert_atom(event_to_atom(ev, sector=sec, gen_date="2026-07-04"))
    yield


def test_days_horizon_excludes_far_events():
    out = select_future_events("2026-07-04", days=30)   # 08-20은 D-47 → 제외
    assert [e["asset"] for e in out] == ["삼성전자"]


def test_days_none_returns_all():
    out = select_future_events("2026-07-04")
    assert len(out) == 2


def test_to_api_dict_shape():
    e = select_future_events("2026-07-04", days=30)[0]
    d = to_api_dict(e)
    assert d == {
        "event_date": "2026-07-08", "dday": 4, "asset": "삼성전자",
        "sector": "반도체", "content": "2Q 실적", "event_kind": "실적발표",
        "entity_scope": "domestic", "confidence": 1, "confirmed": True,
        "affected_stocks": ["삼성전자"],
    }
