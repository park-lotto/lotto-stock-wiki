"""CTA를 요소 목록·구조분석 스키마에 추가했는지 — 요소 업그레이드가 CTA를 다루려면 필요."""
from shopping_shorts import script_generate
from shopping_shorts import structure_analyze


def test_cta_in_elem_labels():
    assert script_generate.ELEM_LABELS.get("cta") == "마무리/CTA"
    assert "cta" in script_generate.ELEM_KEYS


def test_cta_in_structure_schema_optional():
    props = structure_analyze._SCHEMA["properties"]
    assert "cta" in props and props["cta"]["type"] == "string"
    # 기존 분석본(cta 없음)이 깨지지 않도록 required에는 넣지 않는다
    assert "cta" not in structure_analyze._SCHEMA["required"]
