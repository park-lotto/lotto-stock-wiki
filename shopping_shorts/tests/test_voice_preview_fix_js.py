from pathlib import Path
HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")

def test_fix_functions_exist():
    for fn in ["function vpNudge", "function vpResetOffset", "function vpRegenTone", "function vpGateNext"]:
        assert fn in HTML, fn

def test_nudge_calls_offset_route():
    assert "/api/mix/caption_offset/" in HTML

def test_regen_calls_regen_route():
    assert "/regen" in HTML and "/api/mix/tts/" in HTML

def test_gate_checks_heard_yellow():
    # 안 들어본 🟡가 있으면 confirm으로 한 번 묻는다(막지 않음)
    assert "_vpHeard" in HTML and "confirm(" in HTML

def test_nudge_step_is_point_one():
    assert "0.1" in HTML   # ±0.1초 스텝
