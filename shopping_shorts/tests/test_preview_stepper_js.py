from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_stepper_markup_and_functions_exist():
    # ◀▶ 스텝퍼 마크업
    assert 'id="beatStepper"' in HTML
    assert 'onclick="stepBeat(-1)"' in HTML and 'onclick="stepBeat(1)"' in HTML
    assert 'id="beatCount"' in HTML
    # 핵심 함수
    for fn in ["function loadBeatsPreview", "function showBeat", "function stepBeat"]:
        assert fn in HTML, fn


def test_caption_preview_uses_variable_not_hardcoded():
    # 자막 미리보기 텍스트가 전역 변수를 쓰고, 하드코딩 문자열 직접대입은 사라졌다
    assert "PREVIEW_CAP_TEXT" in HTML
    assert "el.textContent='이렇게 자막이 나와요'" not in HTML


def test_entry_loads_beats_preview():
    # step5 진입 자동완성 근처에서 loadBeatsPreview를 호출한다
    assert "loadBeatsPreview()" in HTML
