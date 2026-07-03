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


def test_briefing_run_synthesis_finds_prior_ai_brief_past_recent_raw_alerts(tmp_path, monkeypatch):
    """직전 raw_alert들이 최신 2개를 차지해도, 그보다 오래된 ai_brief 항목을
    prior_headlines로 찾아내야 한다(필터 먼저, 슬라이스 나중)."""
    from datetime import datetime
    p = tmp_path / "market_briefing.json"
    today = datetime.now().strftime("%Y-%m-%d")
    p.write_text(json.dumps({"date": today, "items": [
        {"ts": "09:50", "severity": "gray", "headline": "코스피 등락률 변동",
         "body": None, "kind": "raw_alert"},
        {"ts": "09:49", "severity": "gray", "headline": "프로그램 순매수 변동",
         "body": None, "kind": "raw_alert"},
        {"ts": "09:30", "severity": "yellow", "headline": "외국인 매도 전환",
         "body": "설명입니다", "kind": "ai_brief"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(server, "BRIEFING_PATH", str(p))
    monkeypatch.setattr(server, "_briefing_last_ai_call", {"ts": 0.0})
    monkeypatch.setattr(server, "_NEWS_FEED", {"data": None})

    captured = {}
    def _fake_gemini_text(prompt, keys=None, models=None):
        captured["prompt"] = prompt
        return {"ok": True, "analysis": "헤드라인: 테스트\n본문: 테스트 본문입니다"}
    monkeypatch.setattr(server, "_gemini_text", _fake_gemini_text)

    server._briefing_run_synthesis([{"ts": "09:51", "metric": "J_change_rate",
                                      "from": 0.5, "to": 1.8, "label": "코스피 등락률"}])

    assert "prompt" in captured, "Gemini가 호출되지 않음"
    assert "외국인 매도 전환" in captured["prompt"], (
        "오래된 ai_brief 헤드라인이 prior_headlines에 안 들어감 — 필터/슬라이스 순서 버그")
