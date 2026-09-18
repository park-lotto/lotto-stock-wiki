from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = (ROOT / "out" / "precision20-ui.js").read_text(encoding="utf-8")
CONNECT = (ROOT / "out" / "scene-style-connect.js").read_text(encoding="utf-8")
PRODUCE = (ROOT / "shopping_shorts" / "static" / "scene-style-produce.js").read_text(encoding="utf-8")


def test_even_reference_does_not_auto_shrink_or_scale_x():
    assert "lockedReference=rows[current]?.id==='t11'&&frame.reference_style" in UI
    assert "if(!lockedReference)" in UI
    assert "if(p.id==='t11'&&frame.reference_style)return" in UI


def test_even_contract_blocks_save_when_copy_is_too_long():
    assert "const evenLimits={channel:12,hook1:11,hook2:10,bodyTitle:22,caption:22}" in UI   # 둘째 줄 10자(2026-09-18, 11자면 양끝 잘림)
    assert "validation:()=>templateViolations()" in UI
    assert "const violations=api.validation?.()||[]" in CONNECT


def test_scene_editor_receives_paired_subline_and_copy_family():
    assert "headcopy_subline:STATE.headcopy?.subline" in PRODUCE
    assert "copy_family:STATE.headcopy?.copy_family||STATE.script_copy_family" in PRODUCE
