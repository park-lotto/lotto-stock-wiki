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


def test_beat_action_mismatch_catches_fit5_lie():
    # 바나나 실사고: 나레이션은 '자르다'인데 화면은 '뒤집다' → fit이 5여도 불일치
    beat = {"narration": "바나나 썰어 넣고", "fit": 5,
            "primary": {"seg_id": "s2-4", "scene_desc": "팬케이크를 뒤집는 모습", "action": "뒤집다"}}
    assert backbone.beat_action_mismatch(beat) is True


def test_beat_action_match_ok():
    beat = {"narration": "바나나 썰어 넣고", "fit": 3,
            "primary": {"seg_id": "x", "scene_desc": "칼로 바나나를 써는", "action": "자르다"}}
    assert backbone.beat_action_mismatch(beat) is False


def test_reconcile_swaps_screen_to_matching_action():
    beat = {"narration": "바나나 썰어 넣고", "fit": 5,
            "primary": {"seg_id": "s2-4", "scene_desc": "뒤집는", "action": "뒤집다", "video_id": "BB"}}
    pool = [{"video_id": "S1", "segments": [_seg("S1-9", scene_desc="바나나 써는", action="자르다")]}]
    nb, need_rewrite = backbone.reconcile_beat_by_action(beat, pool)
    assert need_rewrite is False
    assert nb["primary"]["action"] == "자르다" and nb.get("action_fixed") is True


def test_reconcile_flags_rewrite_when_no_clip():
    beat = {"narration": "바나나 썰어 넣고",
            "primary": {"seg_id": "x", "scene_desc": "뒤집는", "action": "뒤집다"}}
    pool = [{"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]  # 자르다 없음
    nb, need_rewrite = backbone.reconcile_beat_by_action(beat, pool)
    assert need_rewrite is True and nb.get("need_rewrite") is True


def test_pick_clips_excludes_backbone_video():
    pool = [{"video_id": "BB", "segments": [_seg("BB-1", action="붓다")]},
            {"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]
    clips = backbone.pick_clips_for_action("붓다", pool, exclude_video="BB")
    assert len(clips) == 1 and clips[0]["video_id"] == "S1"
