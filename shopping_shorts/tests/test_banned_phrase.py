"""금지어 반려(2026-07-29 사장님 확정) — 실측 A/B/C 후보가 '완벽 해결'·'꿀템'·'쾌적하게' 같은
상세페이지 상투어를 반복 사용했는데 프롬프트만으론 안 막혀 오히려 추천작이 위반했다.
_score_candidate가 금지어 포함 후보를 0점으로 강제 반려한다(순수 계산, Gemini 없음)."""
from shopping_shorts import edit_plan


def _beat(narr, sid="s0-0"):
    return {"fit": 5, "primary": {"seg_id": sid}, "alternates": [],
            "narration": narr, "target_seconds": 5.0, "role": "body"}


def test_banned_phrase_hit_true_when_present():
    beats = [_beat("공기 순환으로 꿉꿉한 냄새와 곰팡이 고민까지 완벽 해결했어요.")]
    assert edit_plan._banned_phrase_hit(beats) is True


def test_banned_phrase_hit_false_when_clean():
    beats = [_beat("남편이 화장실만 들어갔다 오면 땀을 뻘뻘 흘리더라고요.")]
    assert edit_plan._banned_phrase_hit(beats) is False


def test_banned_phrase_hit_false_for_empty_beats():
    assert edit_plan._banned_phrase_hit([]) is False


def test_score_candidate_zero_when_banned_phrase_present():
    plan = {"beats": [_beat("화장실 꿉꿉함, 이 무선 실링팬 하나로 한 방에 완벽 해결했어요.")]}
    assert edit_plan._score_candidate(plan) == 0.0


def test_score_candidate_nonzero_for_same_shape_without_banned_phrase():
    plan = {"beats": [_beat("화장실 꿉꿉함, 이 무선 실링팬 하나로 한 방에 잡았어요.")]}
    assert edit_plan._score_candidate(plan) > 0.0


def test_banned_phrase_hit_true_for_inflected_variant():
    # 2026-07-29 실측: 정확일치는 '쾌적하게'만 잡고 '쾌적한'은 놓쳤다(실제 후보에서 발견).
    beats = [_beat("공기가 도니까 이제야 쾌적한 느낌이 드네요.")]
    assert edit_plan._banned_phrase_hit(beats) is True


def test_banned_phrase_fuzzy_false_for_unrelated_word_sharing_suffix():
    # '신세계'와 어간이 다른 무관한 단어('세계')까지 오탐하면 안 된다.
    beats = [_beat("이 제품은 세계 여러 나라에서 팔린다고 하더라고요.")]
    assert edit_plan._banned_phrase_hit(beats) is False


def test_banned_phrase_fuzzy_false_for_short_banned_phrase_synonym():
    # '꿀템'의 동의어('꿀팁')는 어간 자체가 달라 퍼지매칭으로도 못 잡는 게 맞다(오탐 방지 우선).
    beats = [_beat("여름 꿀팁이 궁금하면 댓글 남겨주세요.")]
    assert edit_plan._banned_phrase_hit(beats) is False
