"""자막제거 스위치(#subToggle)는 **스위치 자체를 눌러서** 켜져야 한다 (2026-09-04 실사고).

투명 체크박스(.sw-input, absolute)가 DOM상 .sw-track 앞이라 뒤 형제 track(position:relative)이
위에 그려져, 스위치를 눌러도 아무 일도 안 났다(elementFromPoint = .sw-knob). 제목 label(for=)로만
켜져 "자막제거 버튼 활성화가 안 된다" 제보가 여럿. z-index로 입력을 위에 올린다.
"""
import re
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "shopping_shorts" / "static" / "produce.html"


def _rule(selector):
    src = HTML.read_text(encoding="utf-8")
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", src)
    assert m, f"{selector} 규칙이 없다"
    return m.group(1)


def test_sw_input_stacks_above_track():
    body = _rule(".sw-input")
    assert "position:absolute" in body
    assert re.search(r"z-index\s*:\s*[1-9]", body), "투명 체크박스가 track 아래 깔리면 스위치를 눌러도 안 켜진다"


def test_sw_wrap_is_positioned_parent():
    body = _rule(".sw-wrap")
    assert "position:relative" in body, ".sw-input(absolute)이 스위치 자리에 겹치려면 부모가 positioned여야 한다"


def test_credit_and_toggle_side_by_side():
    body = _rule(".hright")
    assert "flex-direction:row" in body, "사장님 지시(09-04): 크레딧 버튼과 스위치는 옆으로 나란히"
