from pathlib import Path

HTML = (Path(__file__).parent.parent / "static" / "produce.html").read_text(encoding="utf-8")


def test_pace_toggle_present():
    """속도감 모드 체크박스와 setPace 핸들러가 마크업에 있다."""
    assert 'id="paceMode"' in HTML
    assert "setPace(" in HTML
    assert "속도감 모드" in HTML


def test_pace_mode_in_voice_and_body():
    """VOICE에 pace_mode 필드가 있고, voice/apply 요청 body에 실려 나간다."""
    assert "pace_mode" in HTML
    assert "pace_mode:VOICE.pace_mode" in HTML
