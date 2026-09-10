"""전체 자막 위치와 장면별 위치가 충돌해 렌더가 안 움직이던 회귀 방지.

전체 세로 슬라이더/가로 정렬을 바꿔도 beat.cap_xy가 남으면 렌더의 우선순위상
그 장면은 옛 자리를 계속 쓴다. 전체 위치 조작은 설정 저장 뒤 장면별 덮어쓰기를
지우고, 최종 렌더는 그 작업이 끝날 때까지 기다려야 한다.
"""
import pathlib
import re


PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _src() -> str:
    return PRODUCE_HTML.read_text(encoding="utf-8")


def _body(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i:src.index(end, i)]


def test_vertical_slider_commits_global_position_and_clears_scene_overrides():
    src = _src()
    tag = re.search(r'<input id="capY"[^>]+>', src).group(0)
    assert 'oninput="capPositionTouched()"' in tag
    assert 'onchange="saveCapAllPosition()"' in tag


def test_horizontal_alignment_uses_same_global_position_path():
    body = _body(_src(), "function alignCap(where){", "// ══")
    assert "capPositionTouched()" in body
    assert "saveCapAllPosition()" in body


def test_global_position_save_orders_style_before_override_cleanup():
    body = _body(_src(), "async function saveCapAllPosition(){", "// 지워진 자막영역")
    assert "await saveHeadcopy()" in body
    assert "apply_all:true" in body
    assert body.index("await saveHeadcopy()") < body.index("apply_all:true")
    assert "b.cap_xy=null" in body and "b.pos_y_pct=null" in body


def test_final_render_waits_for_global_position_flush():
    body = _body(_src(), "async function renderFinal(){", "/api/mix/render")
    assert "await saveCapAllPosition()" in body
    assert body.index("await saveCapAllPosition()") < body.index("flushApply")


def test_settings_failure_cannot_silently_render_old_position():
    src = _src()
    save_body = _body(src, "async function saveHeadcopy(){", "function jump(")
    render_body = _body(src, "async function renderFinal(){", "/api/mix/render")
    assert "return r.ok" in save_body
    assert "if(!_settingsSaved)" in render_body
