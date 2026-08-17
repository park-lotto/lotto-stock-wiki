"""템플릿 UI — 선택이 STATE.deco.template에 저장되고 로고 슬롯을 안 건드리는가."""
import pathlib

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_template_box_exists():
    assert 'id="tplCards"' in HTML
    assert 'name="tplSpan"' in HTML


def test_picks_into_template_slot_not_overlay():
    """★STATE.deco.overlay(사장님 로고)를 건드리면 로고가 사라진다."""
    i = HTML.index("function pickTemplate")
    j = HTML.index("function setTemplateSpan", i)
    body = HTML[i:j]
    assert "STATE.deco.template" in body
    assert "STATE.deco.overlay" not in body, "템플릿이 로고 슬롯을 덮어쓴다"


def test_span_saved():
    i = HTML.index("function setTemplateSpan")
    body = HTML[i:i + 400]
    assert "span" in body and "saveHeadcopy()" in body


def test_template_url_not_static_prefixed():
    """정적 마운트가 루트라 /static/ 접두사를 쓰면 12장 전부 깨진 이미지가 된다."""
    assert "/static/templates/" not in HTML


def test_overlay_upload_still_present():
    """기존 이미지 오버레이 기능이 살아 있는가(옮기기만 했지 지우지 않았다)."""
    assert 'id="ovFile"' in HTML or "이미지 오버레이" in HTML
