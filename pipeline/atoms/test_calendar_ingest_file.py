import json
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, get_conn
from pipeline.atoms.calendar_ingest import ingest_calendar_file


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _write_cal(tmp_path):
    data = {
        "generated_at": "2026-07-04",
        "macro": [
            {"date": "2026-07-18", "event": "금통위", "type": "금통위",
             "importance": "[HIGH]", "desc": "기준금리 결정", "confirmed": True},
        ],
        "sectors": {
            "반도체": [
                {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
                 "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True},
            ],
        },
    }
    p = tmp_path / "20260704_섹터캘린더.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_ingest_calendar_file_inserts_all(tmp_path):
    n = ingest_calendar_file(str(_write_cal(tmp_path)))
    assert n == 2
    conn = get_conn()
    rows = conn.execute(
        "SELECT sector, asset, content, event_date FROM atoms WHERE event_type='event' ORDER BY event_date"
    ).fetchall()
    conn.close()
    # 종목 이벤트는 asset=종목명, 매크로 이벤트는 company가 없어 asset=sector="매크로"
    # (이벤트명 '금통위'는 content에 보존)
    assert [dict(r)["asset"] for r in rows] == ["삼성전자", "매크로"]
    assert dict(rows[1])["sector"] == "매크로"
    assert "금통위" in dict(rows[1])["content"]


def test_ingest_is_idempotent(tmp_path):
    p = _write_cal(tmp_path)
    ingest_calendar_file(str(p))
    ingest_calendar_file(str(p))
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM atoms").fetchone()["c"]
    conn.close()
    assert n == 2  # INSERT OR REPLACE → 중복 없음
