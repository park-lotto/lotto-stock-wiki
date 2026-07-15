from shopping_shorts.narration_naturalize import naturalize_detail, _sentence_starts

TWO = "감자 찌지 마세요. 이거 하나면 끝이에요."


def _p(intensity, cap=2):
    return {"fillers": {"on": True, "intensity": intensity, "bank": ["음", "아", "그"]},
            "caps": {"max_fillers_per_text": cap, "max_tags_per_beat": 1, "max_tags_total": 3},
            "spoken_style": {"on": False}, "emotion_arc": {"on": False},
            "endings": {"on": False}, "intonation": {"on": False}, "phrasing": {"on": False}}


def test_sentence_starts_finds_each_sentence():
    # 브리프 원안은 [0, 12]였으나 TWO 문자열의 실제 두 번째 문장 시작 오프셋은 11이다
    # (마침표(9)+공백(10) 다음이 "이거"의 '이'(11)). 코드포인트로 직접 검증(off-by-one,
    # 브리프 저작 시점 수기 계산 오류로 판단 — 구현은 브리프 Step3 알고리즘 그대로).
    assert [hex(ord(c)) for c in TWO][:12] == [
        '0xac10', '0xc790', '0x20', '0xcc0c', '0xc9c0', '0x20', '0xb9c8', '0xc138',
        '0xc694', '0x2e', '0x20', '0xc774']
    assert _sentence_starts(TWO) == [0, 11]


def test_filler_count_scales_with_intensity():
    """강도가 오르면 추임새가 실제로 늘어난다(옛 임계형은 항상 1개였다)."""
    low = naturalize_detail(TWO, _p(0.3), beat_index=0, beat_total=1)
    high = naturalize_detail(TWO, _p(1.0), beat_index=0, beat_total=1)
    assert low["applied"]["fillers"] == 1
    assert high["applied"]["fillers"] == 2
    assert low["text"] != high["text"]


def test_low_intensity_skips_some_beats():
    """낮은 강도는 '몇 비트마다 하나' — 모든 비트에 붙지 않는다(도배 방지)."""
    p = _p(0.25)   # every = 4
    got = [naturalize_detail(TWO, p, beat_index=i, beat_total=8)["applied"].get("fillers", 0)
           for i in range(8)]
    assert got == [1, 0, 0, 0, 1, 0, 0, 0]


def test_cap_limits_but_does_not_kill_intensity():
    capped = naturalize_detail(TWO, _p(1.0, cap=1), beat_index=0, beat_total=1)
    assert capped["applied"]["fillers"] == 1
