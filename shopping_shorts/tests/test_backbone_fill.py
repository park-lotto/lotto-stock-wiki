

def test_cta_beat_prefers_completion_shots():
    """CTA 자리 채우기는 완성컷을 먼저 쓴다 — 조리 재방송 방지(2026-08-01 실사고).

    실측(job a75c22f644ad): CTA 비트가 s0의 조리 전과정(설탕붓기→잼섞기→짜넣기→뚜껑덮기)
    4컷을 통째로 끌어와 영상 끝이 "조리 재방송"이 됐다. 세 후보 모두 같은 모양이었다.
    """
    from shopping_shorts import backbone

    def _seg(sid, role, dur=2.0):
        return {"seg_id": sid, "shot_role": role, "start": 0.0, "end": dur,
                "scene_desc": role, "video_id": "s0"}

    pool = [{"video_id": "s0", "segments": [
        _seg("s0-1", "사용중"), _seg("s0-2", "사용중"),
        _seg("s0-3", "완성"), _seg("s0-4", "완성")]}]
    beat = {"role": "cta", "narration": "댓글 남겨주세요",
            "primary": _seg("s0-0", "완성"), "alternates": []}
    out = backbone.fill_clips_to_cover(beat, pool, need=6.0)
    got = [a["seg_id"] for a in out["alternates"]]
    assert got[:2] == ["s0-3", "s0-4"], f"완성컷이 먼저 와야 한다: {got}"


def test_fill_still_uses_other_shots_when_matching_run_out():
    """맞는 계열이 떨어지면 종전대로 채운다 — 재료를 줄이면 프리즈가 돌아온다."""
    from shopping_shorts import backbone

    def _seg(sid, role, dur=2.0):
        return {"seg_id": sid, "shot_role": role, "start": 0.0, "end": dur,
                "scene_desc": role, "video_id": "s0"}

    pool = [{"video_id": "s0", "segments": [_seg("s0-1", "사용중"), _seg("s0-2", "사용중")]}]
    beat = {"role": "cta", "narration": "댓글", "primary": _seg("s0-0", "완성"),
            "alternates": []}
    out = backbone.fill_clips_to_cover(beat, pool, need=6.0)
    assert [a["seg_id"] for a in out["alternates"]] == ["s0-1", "s0-2"]


def test_cta_beat_prefers_completion_shots():
    """CTA 자리 채우기는 완성컷을 먼저 쓴다 — 조리 재방송 방지(2026-08-01 실사고).

    실측(job a75c22f644ad): CTA 비트가 s0의 조리 전과정(설탕붓기→잼섞기→짜넣기→뚜껑덮기)
    4컷을 통째로 끌어와 영상 끝이 "조리 재방송"이 됐다. 세 후보 모두 같은 모양이었다.
    """
    from shopping_shorts import backbone

    def _seg(sid, role, dur=2.0):
        return {"seg_id": sid, "shot_role": role, "start": 0.0, "end": dur,
                "scene_desc": role, "video_id": "s0"}

    pool = [{"video_id": "s0", "segments": [
        _seg("s0-1", "사용중"), _seg("s0-2", "사용중"),
        _seg("s0-3", "완성"), _seg("s0-4", "완성")]}]
    beat = {"role": "cta", "narration": "댓글 남겨주세요",
            "primary": _seg("s0-0", "완성"), "alternates": []}
    out = backbone.fill_clips_to_cover(beat, pool, need=6.0)
    got = [a["seg_id"] for a in out["alternates"]]
    assert got[:2] == ["s0-3", "s0-4"], f"완성컷이 먼저 와야 한다: {got}"


def test_fill_still_uses_other_shots_when_matching_run_out():
    """맞는 계열이 떨어지면 종전대로 채운다 — 재료를 줄이면 프리즈가 돌아온다."""
    from shopping_shorts import backbone

    def _seg(sid, role, dur=2.0):
        return {"seg_id": sid, "shot_role": role, "start": 0.0, "end": dur,
                "scene_desc": role, "video_id": "s0"}

    pool = [{"video_id": "s0", "segments": [_seg("s0-1", "사용중"), _seg("s0-2", "사용중")]}]
    beat = {"role": "cta", "narration": "댓글", "primary": _seg("s0-0", "완성"),
            "alternates": []}
    out = backbone.fill_clips_to_cover(beat, pool, need=6.0)
    assert [a["seg_id"] for a in out["alternates"]] == ["s0-1", "s0-2"]
