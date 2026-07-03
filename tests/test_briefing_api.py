import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

import server
from fastapi.testclient import TestClient


def test_api_market_briefing_returns_stored_items(tmp_path, monkeypatch):
    p = tmp_path / "market_briefing.json"
    from datetime import datetime
    p.write_text(json.dumps({"date": datetime.now().strftime("%Y-%m-%d"),
                              "items": [{"ts": "09:47", "severity": "red",
                                         "headline": "테스트", "body": "본문",
                                         "kind": "ai_brief"}]}), encoding="utf-8")
    monkeypatch.setattr(server, "BRIEFING_PATH", str(p))

    c = TestClient(server.app)
    r = c.get("/api/market_briefing").json()
    assert r["items"][0]["headline"] == "테스트"


def test_api_market_briefing_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "BRIEFING_PATH", str(tmp_path / "missing.json"))
    c = TestClient(server.app)
    r = c.get("/api/market_briefing").json()
    assert r["items"] == []
