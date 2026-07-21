"""사장님 판정 뒤집기(2026-07-21) — intensifier 위치 쉼표/훅꼬리 억제.

2026-07-17 청취판정으로 넣었던 '강조부사 앞 쉼표'와 '훅 마지막어절 강조'가
실사용 대본에서 intensifier("진짜 대박"처럼 부사가 뒤 단어를 직접 수식)를 끊어
'해보세요, 진짜, 대박이에요!'처럼 사투리 억양으로 들린다는 사장님 재판정.
→ intensifier(부사 뒤에 곧바로 한글 내용어)면 쉼표를 넣지 않는다. 부사가
   문장 끝/구두점 앞에 트레일링으로 올 때만(=진짜 강조 자리) 남긴다.
   훅꼬리도 마지막 어절이 서술어 종결이면 강조를 접는다.
"""
from shopping_shorts.narration_naturalize import naturalize, naturalize_detail, merge_profile


def _p(intensity=1.0):
    return {"intonation": {"on": True, "intensity": intensity},
            "fillers": {"on": False}, "spoken_style": {"on": False},
            "endings": {"on": False}, "emotion_arc": {"on": False}, "phrasing": {"on": False}}


def test_intensifier_position_gets_no_comma():
    """부사가 뒤 단어를 직접 수식하면(진짜 대박) 쉼표를 넣지 않는다."""
    d = naturalize_detail("이거 진짜 대박이에요", _p(1.0), beat_index=0, beat_total=1)
    assert d["text"] == "이거 진짜 대박이에요", d["text"]
    assert "intonation" not in d["applied"]


def test_trailing_adverb_still_gets_comma():
    """부사가 문장 끝(구두점 앞)에 트레일링으로 오면 강조 쉼표는 유지된다."""
    d = naturalize_detail("가격이 싼데 완전.", _p(1.0), beat_index=0, beat_total=1)
    assert ", 완전" in d["text"], d["text"]


def test_hook_tail_skips_predicate_ending():
    """훅 마지막 어절이 서술어 종결(…에요/…해요)이면 훅꼬리 강조를 접는다."""
    out = naturalize("감자 쪄먹지만 말고 이렇게 해보세요, 진짜 대박입니다!",
                     merge_profile({}), beat_role="훅")
    assert "진짜, 대박" not in out, out
    assert "진짜 대박" in out or "대박이에요" in out, out


def test_hook_tail_still_fires_on_punchy_word():
    """짧은 punchy 어절(이거)로 끝나는 훅은 그대로 강조한다 — 설계 유지."""
    out = naturalize("요새 인플루언서들 손에 하나씩 들려있는 이거.",
                     merge_profile({}), beat_role="훅")
    assert ", 이거!" in out, out


def test_phrasing_no_comma_before_malgo():
    """세트구문 '지만 말고'는 한 덩어리 — 쉼표로 끊지 않는다."""
    prof = {"phrasing": {"on": True, "intensity": 1.0}, "intonation": {"on": False},
            "fillers": {"on": False}, "spoken_style": {"on": False},
            "endings": {"on": False}, "emotion_arc": {"on": False}}
    d = naturalize_detail("감자 쪄먹지만 말고 구워보세요.", merge_profile(prof),
                          beat_index=0, beat_total=1)
    assert "쪄먹지만, 말고" not in d["text"], d["text"]
