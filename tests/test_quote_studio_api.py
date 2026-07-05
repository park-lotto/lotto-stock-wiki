import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

import server
from fastapi.testclient import TestClient


def test_quote_extract_sse_relays_events(monkeypatch):
    def fake_stream(url, topic, max_segments=None):
        yield {"type": "progress", "phase": "채점", "done": 0, "total": 1}
        yield {"type": "result", "doc": {"topic": topic, "source": "채널A / " + url,
               "quotes": [{"ts": "00:12", "ts_sec": 12.0, "text": "HBM 부족",
                           "tier": 3, "has_visual": False, "heat": 0.0,
                           "stance": "강세", "evidence": "수급", "score": 4,
                           "reasons": ["r"], "media": None}]}}
    monkeypatch.setattr(server._qe, "extract_stream", fake_stream)

    c = TestClient(server.app)
    r = c.post("/yt/quote_extract", json={"url": "https://youtu.be/abc12345678",
                                          "topic": "반도체 고점인가"})
    assert r.status_code == 200
    body = r.text
    assert '"type": "result"' in body
    assert "HBM 부족" in body
    assert '"phase": "채점"' in body or "채점" in body


def test_quote_save_writes_json(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", str(tmp_path))
    c = TestClient(server.app)
    payload = {"url": "https://youtu.be/abc12345678", "topic": "반도체 고점인가",
               "quotes": [{"ts": "00:12", "text": "HBM 부족", "stance": "강세"}]}
    r = c.post("/yt/quote_save", json=payload).json()
    assert r["ok"] is True
    assert r["count"] == 1
    saved = tmp_path / "out" / "quote_studio" / "abc12345678.json"
    assert saved.exists()
    doc = json.loads(saved.read_text(encoding="utf-8"))
    assert doc["quotes"][0]["text"] == "HBM 부족"


def test_quote_extract_requires_url(monkeypatch):
    c = TestClient(server.app)
    r = c.post("/yt/quote_extract", json={"topic": "x"})
    assert r.status_code == 400


def test_quote_extract_url_check_precedes_module_guard(monkeypatch):
    # url 누락은 _qe 유무보다 먼저 판정돼야 함 → 모듈이 없어도(503) url 없으면 400
    monkeypatch.setattr(server, "_qe", None)
    c = TestClient(server.app)
    r = c.post("/yt/quote_extract", json={"topic": "x"})
    assert r.status_code == 400
