import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dashboard"))

import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
import server
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    for ev, sec in [
        ({"date": "2026-07-08", "company": "삼성전자", "event": "2Q 실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}, "반도체"),
        ({"date": "2026-07-25", "company": "HD현대중공업", "event": "2Q 실적",
          "type": "실적발표", "importance": "[MID]", "desc": "", "confirmed": True}, "조선"),
    ]:
        insert_atom(event_to_atom(ev, sector=sec, gen_date="2026-07-04"))
    wl = tmp_path / "watchlist.json"
    wl.write_text(json.dumps({"codes": [{"code": "005930", "name": "삼성전자"}]}), encoding="utf-8")
    monkeypatch.setattr(server, "WATCHLIST_PATH", str(wl))
    yield


def _client():
    return TestClient(server.app)


def test_catalysts_all():
    r = _client().get("/api/catalysts?mine=0&today=2026-07-04").json()
    assert r["count"] == 2
    assert r["events"][0]["asset"] == "삼성전자"
    assert r["events"][0]["dday"] == 4


def test_catalysts_mine_filters_by_watchlist():
    r = _client().get("/api/catalysts?mine=1&today=2026-07-04").json()
    assert [e["asset"] for e in r["events"]] == ["삼성전자"]


def test_catalysts_sector_filter():
    r = _client().get("/api/catalysts?mine=0&sector=조선&today=2026-07-04").json()
    assert [e["asset"] for e in r["events"]] == ["HD현대중공업"]
