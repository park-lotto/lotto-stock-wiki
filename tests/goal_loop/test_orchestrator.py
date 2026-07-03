from scripts.goal_loop import morning_brief as mb


def _patch(monkeypatch, index_moves, critique_pass=True, data=None, infographic_path="ig.png"):
    monkeypatch.setattr(mb, "_ensure_scenario", lambda date: None)   # Stage0 서브프로세스 우회
    monkeypatch.setattr(mb.studio_data, "get_briefing_data",
                        lambda d: (data if data is not None else {"headline": "h", "date": d}))
    monkeypatch.setattr(mb, "_render_card", lambda data, date: "x.png")   # 렌더 우회
    monkeypatch.setattr(mb, "_get_index_moves", lambda: index_moves)
    monkeypatch.setattr(mb.notebook_stage0, "generate_infographic",
                        lambda nb_id, date: infographic_path)
    sent = {"photo": [], "msg": [], "captions": []}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: sent["photo"].append((chat_id, png)) or sent["captions"].append(caption) or True)
    monkeypatch.setattr(mb.viz_card, "send_telegram_message",
                        lambda text, chat_id=None: sent["msg"].append(chat_id) or sent["captions"].append(text) or True)
    monkeypatch.setattr(mb.quality, "critique", lambda data, fn: {"pass": critique_pass, "issues": []})
    return sent


def test_normal_day_sends_to_channel(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    assert [c for c, _p in sent["photo"]] == [None, None]      # 채널(기본 chat_id=None): 텍스트카드+인포그래픽 2회


def test_anomaly_escalates_to_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setenv("OWNER_CHAT_ID", "999")
    sent = _patch(monkeypatch, {"kospi": -3.5, "kosdaq": -2.0})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert [c for c, _p in sent["photo"]] == ["999"]     # 사장님 개인에게만
    assert None not in [c for c, _p in sent["photo"]]    # 채널로 안 감
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


def test_stage0_links_appended_to_caption_on_send(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})
    # _patch()가 _ensure_scenario를 lambda date: None으로 고정하므로, 링크 반환 동작을 검증하려면
    # _patch() 호출 이후에 다시 override해야 한다(monkeypatch는 나중 setattr가 이긴다).
    monkeypatch.setattr(mb, "_ensure_scenario",
                        lambda date: {"notebook_id": "nb1",
                                      "notebook_url": "https://notebooklm.google.com/notebook/nb1",
                                      "report_url": "https://notebooklm.google.com/notebook/nb1"})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    assert "captions" in sent and "notebooklm.google.com/notebook/nb1" in sent["captions"][0]


def test_stage0_returns_none_no_crash(monkeypatch, tmp_path):
    """하위호환: _ensure_scenario가 None을 리턴해도(기존 테스트 monkeypatch 방식) 죽지 않음."""
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})   # _patch가 _ensure_scenario→None으로 설정
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"


def test_infographic_success_sends_second_photo(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setattr(mb, "_ensure_scenario",
                        lambda date: {"notebook_id": "nb-1", "notebook_url": "https://notebooklm.google.com/notebook/nb-1", "report_url": None})
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3}, infographic_path="ig.png")
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    pngs = [p for _c, p in sent["photo"]]
    assert "x.png" in pngs and "ig.png" in pngs   # 텍스트카드 + 인포그래픽 둘 다 전송


def test_infographic_failure_escalates_holds_text_card(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.delenv("OWNER_CHAT_ID", raising=False)
    monkeypatch.setattr(mb, "_ensure_scenario",
                        lambda date: {"notebook_id": "nb-1", "notebook_url": None, "report_url": None})
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3}, infographic_path=None)   # 인포그래픽 실패
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert any("인포그래픽" in reason for reason in r["reasons"])
    assert sent["photo"] == []   # 텍스트카드도 발행 안 됨(둘 다 준비돼야 발행)
