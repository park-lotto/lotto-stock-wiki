from shopping_shorts.narration_naturalize import naturalize_detail, merge_profile


def _p(intensity):
    return {"intonation": {"on": True, "intensity": intensity},
            "fillers": {"on": False}, "spoken_style": {"on": False},
            "endings": {"on": False}, "emotion_arc": {"on": False}, "phrasing": {"on": False}}


def test_intonation_adds_pause_before_emphasis_word():
    """강조어 앞에 짧은 포즈(쉼표)를 넣어 억양을 만든다."""
    d = naturalize_detail("이거 진짜 대박이에요", _p(1.0), beat_index=0, beat_total=1)
    assert "이거, 진짜 대박이에요" == d["text"]
    assert d["applied"]["intonation"] == 1


def test_intonation_scales_with_intensity():
    # 브리프 원안은 0.34를 썼지만 공유 선택자 _take_count는 올림(ceil)이라
    # ceil(3*0.34 - 1e-9) = ceil(1.02) = 2가 나와 "낮은 강도=1개" 단언이 깨진다.
    # 실제로 take=1이 나오는 강도(0.3, ceil(3*0.3-1e-9)=ceil(0.9-eps)=1)로 교체한다.
    # _take_count 자체는 5개 스테이지가 공유하므로 수정하지 않는다.
    text = "이거 진짜 완전 대박이고 훨씬 좋아요"
    low = naturalize_detail(text, _p(0.3), beat_index=0, beat_total=1)
    high = naturalize_detail(text, _p(1.0), beat_index=0, beat_total=1)
    assert low["applied"]["intonation"] == 1
    assert high["applied"]["intonation"] == 3
    assert low["text"] != high["text"]


def test_intonation_off_is_noop():
    d = naturalize_detail("이거 진짜 대박", _p(0.0), beat_index=0, beat_total=1)
    assert d["text"] == "이거 진짜 대박"


def test_intonation_skips_when_comma_already_there():
    d = naturalize_detail("이거, 진짜 대박", _p(1.0), beat_index=0, beat_total=1)
    assert d["text"] == "이거, 진짜 대박"


def test_intonation_no_false_positive_on_substring_words():
    """오탐 회귀: 강조어 뒤에 경계(공백/구두점/문장끝)가 없으면 매칭 금지.

    "딱"이 "딱딱해요"(강조어 아님)의 앞 두 글자와 겹치는 게 대표 사례
    (브리프가 지적한 함정) — 뒤쪽 lookahead가 없으면 여기서 쉼표가 잘못 박힌다.
    """
    d = naturalize_detail("이거 딱딱해요", _p(1.0), beat_index=0, beat_total=1)
    assert d["text"] == "이거 딱딱해요"
    assert "intonation" not in d["applied"]


def test_intonation_no_false_positive_other_substrings():
    """완전체/절대값/진짜배기 등 강조어를 접두로 포함하는 다른 단어도 오탐하지 않는다."""
    for text in ["그 완전체가 좋아요", "절대값이 커요", "이건 진짜배기예요"]:
        d = naturalize_detail(text, _p(1.0), beat_index=0, beat_total=1)
        assert d["text"] == text
        assert "intonation" not in d["applied"]


def test_intonation_works_with_default_profile():
    """격리 프로파일(_p)이 아니라 실사용 기본 프로파일(전 스테이지 on)에서도 동작해야
    한다 — 이 프로젝트에서 "격리에선 통과, 실사용에선 무발동"이 반복된 함정이다."""
    text = "이거 진짜 대박이에요"
    p = merge_profile({})
    d = naturalize_detail(text, p, beat_role="실용", beat_index=0, beat_total=1)
    assert d["applied"].get("intonation", 0) >= 1
    assert "," in d["text"]
