from shopping_shorts.narration_naturalize import naturalize_detail, _take_count


def test_take_count_is_proportional_and_ceils():
    """후보 1개짜리 짧은 문장도 낮은 강도에서 반영된다(내림이면 0이라 계단이 된다)."""
    assert _take_count(0, 0.5) == 0
    assert _take_count(1, 0.3) == 1        # 옛 int() 내림이면 0 → 버그였던 지점
    assert _take_count(2, 0.5) == 1
    assert _take_count(2, 1.0) == 2
    assert _take_count(4, 0.5) == 2
    assert _take_count(3, 0.0) == 0


def test_spoken_style_applies_at_low_intensity():
    p = {"spoken_style": {"on": True, "intensity": 0.3}, "fillers": {"on": False},
         "emotion_arc": {"on": False}, "endings": {"on": False}, "intonation": {"on": False}}
    d = naturalize_detail("이거 정말 좋습니다", p, beat_index=0, beat_total=1)
    assert "좋아요" in d["text"]
    assert d["applied"]["spoken_style"] == 1


def test_endings_works_without_period():
    """실제 대본엔 마침표가 있지만 튜닝 코퍼스엔 없다 — 종결어미도 대상이라야 양쪽에서 동작."""
    p = {"endings": {"on": True, "intensity": 1.0}, "fillers": {"on": False},
         "emotion_arc": {"on": False}, "spoken_style": {"on": False}, "intonation": {"on": False}}
    d = naturalize_detail("이거 진짜 좋아요", p, beat_index=0, beat_total=1)
    assert d["text"].endswith("…")
    assert d["applied"]["endings"] == 1


def test_endings_still_converts_periods():
    p = {"endings": {"on": True, "intensity": 1.0}, "fillers": {"on": False},
         "emotion_arc": {"on": False}, "spoken_style": {"on": False}, "intonation": {"on": False}}
    d = naturalize_detail("감자 찌지 마세요. 이거 하나면 끝.", p, beat_index=0, beat_total=1)
    assert "마세요…" in d["text"]
