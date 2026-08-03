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


def test_fun_intensity_detects_strong_device():
    r = tone_score.fun_intensity("예전엔 맨날 실패했는데 이제는 한 번에 성공해요")  # before/after
    assert r["has_strong"] is True and "before_after" in r["devices"]


def test_fun_intensity_detects_twist():
    r = tone_score.fun_intensity("맛있어 보이죠? 근데 알고보니 이게 다이어트 음식이에요")
    assert r["has_strong"] is True and "반전" in r["devices"]


def test_fun_intensity_flags_plain_story():
    r = tone_score.fun_intensity("바나나를 팬에 올리고 계란을 부어서 구웠어요. 맛있게 먹었어요.")
    assert r["has_strong"] is False and r["needs_regen"] is True


def test_empty_is_zero():
    r = tone_score.score_conversational("")
    assert r["score"] == 0.0 and r["needs_review"] is False


def test_ending_diversity_monotonic():
    """⚠️ 2026-07-30(v2): 기준이 '끝 2음절'에서 **어미 유형**으로 바뀌었다.

    옛 테스트는 "해요/봐요/가요" > "합니다×3"을 기대했는데, 새 기준으로는 앞의 셋도
    전부 밋밋한 평서(PLAIN) 한 종류라 **똑같이 단조롭다** — 그게 이 수정의 핵심이다
    (사장님 제보: "다 ~했어요로 끊긴다"를 옛 지표가 '다양하다'고 판정했다).
    그래서 비교 대상을 '진짜로 어미를 섞은 대본'으로 바꾼다.
    """
    varied = "그냥 버리지 마세요. 걸려 있는 거 있죠? 만든 거라지 뭐예요. 향이 퍼지더라구요."
    assert tone_score.ending_diversity(varied) > \
           tone_score.ending_diversity("해요. 봐요. 가요.")
    assert tone_score.ending_diversity("해요. 봐요. 가요.") == \
           tone_score.ending_diversity("합니다. 합니다. 합니다.")


def test_borderline_defers_to_gemini_when_provided():
    # 경계선 밴드로 밀어넣고 call이 점수를 덮는지
    text = "제품이 좋습니다. 이거 써봤어요. 괜찮네요."
    base = tone_score.score_conversational(text)
    if base["needs_review"]:
        r = tone_score.score_conversational(text, call=lambda t: {"score": 0.95})
        assert r["score"] == 0.95 and r["needs_review"] is False
        assert "gemini재판" in r["flags"]
