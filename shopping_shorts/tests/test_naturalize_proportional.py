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


def _endings_only(intensity):
    return {"endings": {"on": True, "intensity": intensity}, "spoken_style": {"on": False},
            "pronunciation": {"on": False}, "phrasing": {"on": False},
            "fillers": {"on": False}, "emotion_arc": {"on": False}, "intonation": {"on": False}}


def test_endings_no_false_positive_on_adverb_and_noun_tails():
    """Critical1 재현 — 옛 `(요|죠|다)(?=\\s|$)`는 부사 '다'와 명사 꼬리 '요'를
    종결어미로 오인했다(2026-07-15 컨트롤러 실측, 기본 강도 0.3에서도 재현).
    강도를 1.0으로 줘도(=오탐이 더 잘 드러나는 조건) 여전히 오탐이 없어야 한다."""
    p = _endings_only(1.0)
    # '다'(부사) 뒤에 `…`가 붙으면 안 된다 — 진짜 종결어미(돼요/들어있어요/없어요)는
    # 목록에 없는 형태라 잡히지 않아도(false negative) 안전하다. 여기서 보장하는 건
    # 딱 하나 — '다'/'중요'/'필요'에 `…`가 붙지 않는다는 것뿐.
    assert naturalize_detail("이거 하나면 다 돼요", p)["text"] == "이거 하나면 다 돼요"
    assert "다…" not in naturalize_detail("모두 다 들어있어요", p)["text"]
    assert "중요…" not in naturalize_detail("중요 포인트예요", p)["text"]
    assert "다…" not in naturalize_detail("재료 다 필요 없어요", p)["text"]
    assert "필요…" not in naturalize_detail("재료 다 필요 없어요", p)["text"]


def test_endings_catches_real_script_endings():
    """서버 실측 대본 5줄 — 문장 끝(종결어미)이 실제로 `…`를 받는다."""
    p = _endings_only(1.0)
    lines = [
        ("감자 찌지 마세요. 집에 있는 이것 하나면 역대급 간식이 탄생합니다.", "탄생합니다…"),
        ("번거롭게 튀기지 마세요. 기름 한 방울 없어도 밖에서 파는 것보다 훨씬 바삭해지니까요.",
         "바삭해지니까요…"),
        ("아이들 건강 간식은 물론, 남편 맥주 안주로도 이만한 게 없거든요.", "없거든요…"),
        ("속은 쫀득하고 겉은 과자처럼 바삭해요.", "바삭해요…"),
        ("단순히 예쁜 줄만 알았는데 실내 열기는 빨아들이고 공기는 정화해 주더라고요.",
         "주더라고요…"),
    ]
    for src, expect_tail in lines:
        out = naturalize_detail(src, p)["text"]
        assert out.endswith(expect_tail), (src, out)


def test_endings_mixed_dot_and_tail_selected_by_position():
    """Important1 — dot 후보와 tail 후보가 섞였을 때 `cands.sort()`가 위치순으로
    고른다(타입별로 뭉쳐 고르지 않는다)는 것을 고정한다. 첫 후보가 tail이고 그
    다음이 dot이라, sort()가 없으면(=dot을 먼저 모아 리스트에 넣던 구코드 순서)
    강도 0.3에서 엉뚱하게 가운데 dot이 먼저 뽑힌다."""
    text = "좋아요 그리고 예뻐요. 진짜 좋아요"
    d03 = naturalize_detail(text, _endings_only(0.3))
    assert d03["text"] == "좋아요… 그리고 예뻐요. 진짜 좋아요"   # 가장 앞(tail)만 선택
    assert d03["applied"]["endings"] == 1
    d06 = naturalize_detail(text, _endings_only(0.6))
    assert d06["text"] == "좋아요… 그리고 예뻐요… 진짜 좋아요"   # 앞의 2개(tail, dot)
    assert d06["applied"]["endings"] == 2


def test_endings_tail_only_proportional():
    """tail 후보만 있는 입력에서 비례 동작(0.3→1곳, 0.6→2곳)을 고정한다 —
    이전엔 tail 비례에 대한 회귀 보호가 전혀 없었다."""
    text = "정말 좋아요 진짜 없어요 완전 좋네요"   # tail 후보 3개(아요/어요/네요)
    d03 = naturalize_detail(text, _endings_only(0.3))
    assert d03["text"] == "정말 좋아요… 진짜 없어요 완전 좋네요"
    assert d03["applied"]["endings"] == 1
    d06 = naturalize_detail(text, _endings_only(0.6))
    assert d06["text"] == "정말 좋아요… 진짜 없어요… 완전 좋네요"
    assert d06["applied"]["endings"] == 2
