from shopping_shorts.narration_naturalize import naturalize_detail


def test_applied_counts_what_actually_happened():
    """적용 횟수가 실제 변경과 일치한다.

    브리프 원안은 {"naturalness": 1.0}을 프로파일로 썼지만 `naturalness`는
    아직 코드에 없는 노브(Task 7 예정)라 여기서 쓰면 DEFAULT_PROFILE의 기본
    강도에 우연히 얹혀 통과할 뿐이다(Task 1 리뷰 Important 지적). 의도가 드러나게
    normalize·emotion_arc만 명시적으로 켠 프로파일로 바꾼다.
    """
    p = {"normalize": {"on": True}, "emotion_arc": {"on": True, "intensity": 1.0}}
    d = naturalize_detail("50% 할인입니다. 지금 확인해보세요.",
                          p, beat_role="CTA", beat_index=0, beat_total=1)
    assert d["applied"]["normalize"] >= 1      # 50% → 오십 퍼센트
    assert d["applied"]["emotion_arc"] == 1    # CTA → [excited]
    assert "오십 퍼센트" in d["text"]


def test_applied_zero_when_stage_has_nothing_to_do():
    """할 일이 없으면 0 — 이게 '죽은 스테이지'를 드러낸다."""
    p = {"normalize": {"on": True}}
    d = naturalize_detail("그냥 평범한 문장",
                          p, beat_role="훅", beat_index=0, beat_total=1)
    assert d["applied"].get("normalize", 0) == 0   # 숫자·기호 없음
