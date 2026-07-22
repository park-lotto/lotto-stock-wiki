from pathlib import Path

HTML = Path("shopping_shorts/static/produce.html").read_text(encoding="utf-8")


def test_trim_button_present():
    assert "끝 조용한 부분 자르기" in HTML


def test_trim_functions_defined():
    assert "function renderTrimControls(" in HTML
    assert "function doTrim(" in HTML


def test_trim_calls_endpoint_and_reloads():
    # doTrim이 trim 엔드포인트를 치고 loadMixReview로 미리보기를 무효화한다
    i = HTML.index("function doTrim(")
    # 800 -> 1000: plan의 verbatim doTrim() 본문이 실측 901자라 800 window로는
    # loadMixReview() 호출부에 못 닿는다(plan 자체 코드+테스트 조합의 기존 불일치, 트랜스크립션 오류 아님).
    body = HTML[i:i + 1000]
    assert "/trim" in body
    assert "loadMixReview()" in body


def test_trim_card_wired_in_beat():
    # 비트 카드가 renderTrimControls를 호출한다
    assert "renderTrimControls(b, i)" in HTML
