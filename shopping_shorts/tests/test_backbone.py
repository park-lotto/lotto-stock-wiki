from shopping_shorts import backbone


def _seg(seg_id, text="", scene_desc="", action=None):
    d = {"seg_id": seg_id, "start": 0, "end": 2, "text": text, "scene_desc": scene_desc}
    if action is not None:
        d["action"] = action
    return d


def test_segment_action_reads_stored_tag():
    assert backbone.segment_action(_seg("A", action="붓다")) == "붓다"


def test_segment_action_falls_back_to_dict():
    assert backbone.segment_action(_seg("A", text="뚜껑을 당겨서 뜯어요")) == "당기다"


def test_coverage_full_when_pool_has_all_actions():
    backbone_src = {"video_id": "BB", "segments": [
        _seg("BB-1", action="붓다"), _seg("BB-2", action="섞다")]}
    pool = [{"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]},
            {"video_id": "S2", "segments": [_seg("S2-1", action="섞다")]}]
    r = backbone.coverage(backbone_src, pool)
    assert r["coverage_pct"] == 1.0
    assert r["uncovered"] == []


def test_coverage_reports_uncovered_actions():
    backbone_src = {"video_id": "BB", "segments": [
        _seg("BB-1", action="붓다"), _seg("BB-2", action="자르다")]}
    pool = [{"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]
    r = backbone.coverage(backbone_src, pool)
    assert r["coverage_pct"] == 0.5
    assert r["uncovered"] == ["자르다"]


def test_pick_clips_excludes_backbone_video():
    pool = [{"video_id": "BB", "segments": [_seg("BB-1", action="붓다")]},
            {"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]
    clips = backbone.pick_clips_for_action("붓다", pool, exclude_video="BB")
    assert len(clips) == 1 and clips[0]["video_id"] == "S1"
