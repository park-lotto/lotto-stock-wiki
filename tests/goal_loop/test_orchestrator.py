import json
from scripts.goal_loop import morning_brief as mb

def _patch(monkeypatch, index_moves, critique_pass=True):
    monkeypatch.setattr(mb.studio_data, "get_briefing_data", lambda d: {"headline": "h", "date": d})
    monkeypatch.setattr(mb, "_render_card", lambda data, date: "x.png")   # 렌더 우회
    monkeypatch.setattr(mb, "_get_index_moves", lambda: index_moves)
    sent = {}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: sent.setdefault("chat_id", chat_id) or True)
    monkeypatch.setattr(mb.quality, "critique", lambda data, fn: {"pass": critique_pass, "issues": []})
    return sent

def test_normal_day_sends_to_channel(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    assert sent["chat_id"] is None      # 채널(기본)

def test_anomaly_escalates_to_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setenv("OWNER_CHAT_ID", "999")
    sent = _patch(monkeypatch, {"kospi": -3.5, "kosdaq": -2.0})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert sent["chat_id"] == "999"     # 사장님 개인
    assert mb.pending.read() is not None
