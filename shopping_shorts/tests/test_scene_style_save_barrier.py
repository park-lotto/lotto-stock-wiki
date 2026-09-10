from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "produce.html").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_zoom_and_highlight_edit_plan_writes_take_job_lock():
    zoom = APP.split("def api_produce_mix_scenezoom", 1)[1].split("def _scenezoom_locked", 1)[0]
    hl = APP.split("def api_produce_mix_scenehl", 1)[1].split("def _scenehl_locked", 1)[0]
    assert "with _plan_lock(job_id):" in zoom
    assert "with _plan_lock(job_id):" in hl


def test_debounced_scene_saves_capture_target_and_values_immediately():
    hl = HTML.split("function _hlSaveSoon(){", 1)[1].split("async function _hlSave", 1)[0]
    zoom = HTML.split("function _zoomSaveSoon(){", 1)[1].split("async function _zoomSaveAll", 1)[0]
    assert "_HL_PENDING=b ? {b, payload:" in hl
    assert "_ZOOM_PENDING=_zoomSaveSnapshot()" in zoom
    assert "seen=new Set()" in zoom  # flattened cuts send one request per real beat


def test_final_render_waits_for_every_scene_style_save_and_fails_closed():
    render = HTML.split("async function renderFinal(){", 1)[1].split("async function pollFinal", 1)[0]
    assert "await flushSceneStyleSaves()" in render
    assert "장면꾸미기 저장 실패 — 렌더하지 않았어요" in render
    assert "장면 편집 저장 실패 — 렌더하지 않았어요" in render
    assert "렌더는 계속" not in render


def test_settings_saves_are_serialized_in_call_order():
    body = HTML.split("async function saveHeadcopy(){", 1)[1].split("function jump", 1)[0]
    assert "_HEADCOPY_SAVE_Q.catch(()=>{}).then" in body
    assert "const body=JSON.stringify" in body


def test_highlight_changes_final_clean_cache_signature():
    from shopping_shorts.mix_pipeline import _plan_signature

    base = {"beats": [{"beat_idx": 0, "target_seconds": 2.0}]}
    highlighted = {"beats": [{"beat_idx": 0, "target_seconds": 2.0,
                               "scene_hl": {"on": True, "mode": "spot", "shape": "round",
                                            "cx": .3, "cy": .4, "r": .2, "zoom": 2.0}}]}
    assert _plan_signature(base) != _plan_signature(highlighted)
