from shopping_shorts.narration_naturalize import naturalize_detail, _tag_priority

ROLES = ["훅", "페인포인트", "반전", "실용", "CTA"]


def _p(intensity):
    return {"emotion_arc": {"on": True, "intensity": intensity},
            "fillers": {"on": False}, "spoken_style": {"on": False},
            "endings": {"on": False}, "intonation": {"on": False}, "phrasing": {"on": False}}


def test_tag_priority_puts_hook_and_cta_first():
    """태그 예산이 적으면 훅과 마지막(CTA)부터 — 가장 중요한 자리."""
    assert _tag_priority(5)[:2] == [0, 4]


def test_tagged_beat_count_scales_with_intensity():
    def tagged(intensity):
        return sum(
            naturalize_detail("문장이에요", _p(intensity), beat_role=r,
                              beat_index=i, beat_total=len(ROLES))["applied"].get("emotion_arc", 0)
            for i, r in enumerate(ROLES)
        )
    # 페인포인트는 무태그(설계)라 최대는 4
    assert tagged(0.2) == 1
    assert tagged(0.2) < tagged(0.6) < tagged(1.0)


def test_low_intensity_tags_hook_only():
    hook = naturalize_detail("문장이에요", _p(0.2), beat_role="훅",
                             beat_index=0, beat_total=5)
    mid = naturalize_detail("문장이에요", _p(0.2), beat_role="반전",
                            beat_index=2, beat_total=5)
    assert hook["text"].startswith("[curious]")
    assert mid["text"] == "문장이에요"


def test_max_tags_total_gate_zero_blocks_tagging_and_bump():
    """Task2가 고친 버그 재발 방지: max_tags_total<=0이면 태그도 안 붙고
    applied에도 안 찍혀야 한다(사후 제거만 하고 bump는 이미 찍힌 상태였던 과거 버그)."""
    profile = _p(1.0)
    profile["caps"] = {"max_tags_total": 0, "max_tags_per_beat": 1, "max_fillers_per_text": 2}
    out = naturalize_detail("문장이에요", profile, beat_role="훅", beat_index=0, beat_total=5)
    assert "[curious]" not in out["text"]
    assert out["applied"].get("emotion_arc", 0) == 0
