from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_caption_drag_locks_target_beat_before_autoplay_can_advance():
    body = HTML.split("function bindCapDrag(){", 1)[1].split("async function saveCapDrag", 1)[0]
    assert "dragBeat=(typeof _curBeat==='function')?_curBeat():null" in body
    assert "const b=dragBeat" in body
    assert "saveCapDrag(dragBeat, dragScope, dragSceneNo, dragSeg)" in body
    assert "CAP_SEQ_GEN++; CAP_PAUSED=true" in body


def test_caption_save_uses_locked_beat_and_updates_all_cut_previews():
    body = HTML.split("async function saveCapDrag", 1)[1].split("async function saveCapAllPosition", 1)[0]
    assert "const b=targetBeat ||" in body
    assert "beat_idx:_beatNo(b)" in body
    assert "seg_idx:segNo" in body
    assert "_capApplyToBeat(b,{cap_xy_segs:" in body
