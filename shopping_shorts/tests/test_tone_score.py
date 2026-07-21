from shopping_shorts import tone_score


def test_conversational_beats_summary_style():
    convo = "이거 진짜 대박이에요. 저는 이렇게 써봤어요. 한번 해보세요."
    summary = "제품이 우수합니다. 성능이 뛰어납니다. 만족도가 높습니다."
    sc = tone_score.score_conversational(convo)["score"]
    ss = tone_score.score_conversational(summary)["score"]
    assert sc > ss


def test_formal_enders_flagged():
    r = tone_score.score_conversational("이것은 좋습니다. 아주 훌륭합니다.")
    assert any("문어체" in f for f in r["flags"])
    assert r["score"] < 0.7


def test_ai_smell_flagged():
    r = tone_score.score_conversational("확인하셨어요? 너무 좋아합니다 정말.",
                                        negatives=["직접 확인해보세요"])
    assert any("AI냄새" in f for f in r["flags"])


def test_empty_is_zero():
    r = tone_score.score_conversational("")
    assert r["score"] == 0.0 and r["needs_review"] is False


def test_ending_diversity_monotonic():
    assert tone_score.ending_diversity("해요. 봐요. 가요.") > \
           tone_score.ending_diversity("합니다. 합니다. 합니다.")


def test_borderline_defers_to_gemini_when_provided():
    # 경계선 밴드로 밀어넣고 call이 점수를 덮는지
    text = "제품이 좋습니다. 이거 써봤어요. 괜찮네요."
    base = tone_score.score_conversational(text)
    if base["needs_review"]:
        r = tone_score.score_conversational(text, call=lambda t: {"score": 0.95})
        assert r["score"] == 0.95 and r["needs_review"] is False
        assert "gemini재판" in r["flags"]
