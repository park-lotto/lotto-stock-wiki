from briefing_digest import format_trigger, DigestBatcher, format_daily


def test_format_trigger_has_events_and_verdict():
    txt = format_trigger(
        [{"label": "외인 순매도→순매수 전환", "major": True}],
        {"verdict": {"tone": "🟢위험선호", "line": "외인 매수 유지"},
         "narrative": "9:45 저점 이후 반등.\n미선물 우호적.", "_model": "claude:opus"})
    assert "외인 순매도→순매수 전환" in txt
    assert "외인 매수 유지" in txt
    assert "opus" in txt


def test_batcher_major_immediate_minor_buffered():
    b = DigestBatcher(minor_interval_s=900)
    now = 1000.0
    imm = b.add([{"label": "big", "major": True}], {"verdict": {"line": "x"}}, now)
    assert imm is not None
    buf = b.add([{"label": "small", "major": False}], {"verdict": {"line": "y"}}, now + 10)
    assert buf is None
    flush = b.add([{"label": "small2", "major": False}], {"verdict": {"line": "z"}}, now + 1000)
    assert flush is not None and "small" in flush


def test_format_daily_counts():
    rows = [{"fired_events": [{"type": "investor_flip"}], "noise_flag": False},
            {"fired_events": [{"type": "sector_surge"}], "noise_flag": True}]
    txt = format_daily(rows)
    assert "2" in txt
    assert "노이즈" in txt
