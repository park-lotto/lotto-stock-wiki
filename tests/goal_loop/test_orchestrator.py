from scripts.goal_loop import morning_brief as mb


def _patch(monkeypatch, index_moves, critique_pass=True, data=None):
    monkeypatch.setattr(mb, "_ensure_scenario", lambda date: None)   # Stage0 서브프로세스 우회
    monkeypatch.setattr(mb.studio_data, "get_briefing_data",
                        lambda d: (data if data is not None else {"headline": "h", "date": d}))
    monkeypatch.setattr(mb, "_render_card", lambda data, date: "x.png")   # 렌더 우회
    monkeypatch.setattr(mb, "_get_index_moves", lambda: index_moves)
    sent = {"photo": [], "msg": []}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: sent["photo"].append(chat_id) or True)
    monkeypatch.setattr(mb.viz_card, "send_telegram_message",
                        lambda text, chat_id=None: sent["msg"].append(chat_id) or True)
    monkeypatch.setattr(mb.quality, "critique", lambda data, fn: {"pass": critique_pass, "issues": []})
    return sent


def test_normal_day_sends_to_channel(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    assert sent["photo"] == [None]      # 채널(기본 chat_id=None) 1회


def test_anomaly_escalates_to_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setenv("OWNER_CHAT_ID", "999")
    sent = _patch(monkeypatch, {"kospi": -3.5, "kosdaq": -2.0})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert sent["photo"] == ["999"]     # 사장님 개인에게만
    assert None not in sent["photo"]    # 채널로 안 감
    assert mb.pending.read() is not None


def test_failclosed_no_owner_never_sends_to_channel(monkeypatch, tmp_path):
    """I1: OWNER_CHAT_ID 없으면 이상징후 ⚠️를 채널로 절대 안 보냄(대기만)."""
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.delenv("OWNER_CHAT_ID", raising=False)
    sent = _patch(monkeypatch, {"kospi": -3.5, "kosdaq": -2.0})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert sent["photo"] == []          # 채널·개인 어디에도 발송 안 함
    assert mb.pending.read() is not None  # 대기함엔 저장됨


def test_empty_data_escalates_never_fabricates(monkeypatch, tmp_path):
    """C1: 빈 데이터면 quality.revise에 넣지 않고 즉시 에스컬레이션, 채널 발행 안 함."""
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.delenv("OWNER_CHAT_ID", raising=False)
    revised = {"n": 0}
    monkeypatch.setattr(mb.quality, "revise", lambda d, i, fn: revised.__setitem__("n", revised["n"] + 1) or d)
    sent = _patch(monkeypatch, {"kospi": 0.1, "kosdaq": 0.1},
                  data={"headline": "", "lines": []})   # 빈 콘텐츠
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert sent["photo"] == []          # 채널 발행 안 함
    assert revised["n"] == 0            # revise(헛소리 생성) 절대 호출 안 됨


def test_error_escalates_not_silent(monkeypatch, tmp_path):
    """I2: 예외 발생해도 침묵하지 않고 대기 저장(+가능하면 알림)."""
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setattr(mb, "_ensure_scenario", lambda date: None)
    monkeypatch.setattr(mb.studio_data, "get_briefing_data",
                        lambda d: (_ for _ in ()).throw(RuntimeError("boom")))
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert any("실패" in x for x in r["reasons"])
    assert mb.pending.read() is not None
