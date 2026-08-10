"""수집 후 대본은행 자동적재 결과 보고 엔드포인트."""
import json
from fastapi.testclient import TestClient
import shopping_shorts.app as app_mod
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    Store(app_mod.DB_PATH)
    return TestClient(app_mod.app)


def test_report_none_before_any_run(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/bank/ingest_report").json() == {"ok": True, "report": {"status": "none"}}


def test_report_reflects_last_setting(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    rep = {"status": "done", "date": "2026-07-22", "added_sources": 5,
           "added_items": 12, "skipped_dup": 3, "by_bucket": {"hook": 5}}
    Store(app_mod.DB_PATH).set_setting("bank_ingest_last", json.dumps(rep, ensure_ascii=False))
    got = c.get("/api/bank/ingest_report").json()
    assert got["ok"] is True
    assert got["report"]["added_sources"] == 5
    assert got["report"]["by_bucket"]["hook"] == 5
