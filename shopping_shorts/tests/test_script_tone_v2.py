"""대본 고도화 v2 — 어미 유형·감각어 채점 + 훅 중복 + 말투 재생성 게이트(2026-07-30).

사장님 제보: "~했어요 단문으로만 끊긴다. '~하는 거 있죠?/~하더라구요' 같은 생생한 말투를
원하는데 적용이 안 된다."

실측 진단(라이브 job 후보 9개 전량):
- 프롬프트엔 어미 지시가 이미 있었다(07-29). 안 지켜진 게 아니라 **검사가 헛돌았다**:
  tone_score가 '끝 2음절'을 봐서 세요/네요/어요/래요를 서로 다른 어미로 셌고,
  전부 '~요'로 끝나는 대본이 0.71로 임계 0.5를 통과했다.
- 감각어 지시도 있었지만 채점에 없어 형용사 0개짜리도 만점이었다.
- 감점만 있고 재생성이 없어, 후보가 전부 밋밋해도 그중 최선이 그대로 나갔다.

여기서 못 박는 것: 위 세 구멍이 다시 열리지 않게 한다.
"""
import pytest

from shopping_shorts import edit_plan, tone_score


# ── 1. 어미를 '음절'이 아니라 '유형'으로 본다 ────────────────────────────
def test_all_yo_endings_are_not_diverse():
    """★뿌리 회귀: 실제로 나갔던 대본. 전부 '~요'인데 예전엔 0.71로 통과했다."""
    real = ("찌꺼기 버리지 마세요.\n방마다 쿠키가 있네요.\n커피향이 나서 물어봤어요.\n"
            "찌꺼기로 만든 방향제래요.\n습기 잡는 꿀팁이라 오래 써요.\n비법은 댓글 남겨주세요.")
    assert tone_score.ending_diversity(real) < 0.5, "전부 ~요인데 다양하다고 판정하면 안 된다"


def test_lively_endings_are_diverse():
    """사장님이 원한 말투는 통과해야 한다(과잉 감점 방지)."""
    good = ("커피 찌꺼기 그냥 버리지 마세요.\n방마다 쿠키가 걸려 있는 거 있죠?\n"
            "홈카페 찌꺼기로 만든 거라지 뭐예요.\n집에 오자마자 저도 찍어봤거든요.\n"
            "곰팡이 없이 은은한 향이 퍼지더라구요.")
    assert tone_score.ending_diversity(good) >= 0.5


@pytest.mark.parametrize("sent,expected", [
    ("방마다 쿠키가 걸려 있는 거 있죠", "QUESTION"),
    ("향이 퍼지더라구요", "LIVE"),
    ("저도 찍어봤거든요", "LIVE"),
    ("만든 거라지 뭐예요", "LIVE"),
    ("그냥 버리지 마세요", "IMPERATIVE"),
    ("정말 좋아하네요", "PLAIN"),
    ("바로 만들어봤어요", "PLAIN"),
])
def test_ending_type_classification(sent, expected):
    assert tone_score.ending_type(sent) == expected


def test_plain_majority_is_penalized():
    """밋밋한 평서가 과반이면 감점 — 프롬프트의 '절반 넘기지 마라'와 짝."""
    plain = "좋아요.\n편해요.\n빨라요.\n깨끗해요.\n만족해요."
    assert "평서과다" in " ".join(tone_score.score_conversational(plain)["flags"])


def test_no_lively_ending_is_flagged():
    plain = "이걸 샀어요.\n집에 왔어요.\n바로 써봤어요.\n좋았어요."
    assert "생생어미0" in tone_score.score_conversational(plain)["flags"]


# ── 2. 감각어를 센다(사장님: "감각어를 풍부하게") ──────────────────────
def test_sensory_counts_real_words_not_intensifiers():
    """'너무·정말·진짜'는 감각어가 아니라 강조어다 — 실측에서 부사 대부분이 이것이었다."""
    p = tone_score.sensory_profile("입에서 사르르 녹고 폭신한 게 정말 너무 진짜 좋아요")
    assert {"사르르", "폭신"} <= set(p["hits"])
    assert p["intensifiers"] == 3
    assert "정말" not in p["hits"]


def test_short_onomatopoeia_needs_word_boundary():
    """1음절 의태어는 경계를 봐야 오탐이 없다('확인'의 '확'은 감각어가 아니다)."""
    assert "확" not in tone_score.sensory_profile("확인해 주세요")["hits"]
    assert "확" in tone_score.sensory_profile("냄새가 확 퍼져요")["hits"]


def test_zero_sensory_is_flagged():
    """★프롬프트가 감각어를 요구하는데 채점이 안 보면 지시가 무시된다(형용사 0개도 만점이었다)."""
    flat = ("이 제품을 샀습니다만 좋아요.\n사용이 편해요.\n결과도 만족스러워요.\n"
            "다들 한번 써보시면 좋겠어요.\n가격도 괜찮아요.")
    assert "감각어0" in tone_score.score_conversational(flat)["flags"]


def test_rich_sensory_scores_higher_than_flat():
    flat = "향이 좋아요. 냄새가 사라져요. 기분이 좋아요. 다들 만족해요."
    rich = "향긋한 냄새가 확 퍼져요. 꿉꿉하던 게 싹 빠지더라구요. 보송해진 게 느껴지는 거 있죠?"
    assert tone_score.score_conversational(rich)["score"] > \
           tone_score.score_conversational(flat)["score"]


# ── 3. 훅 중복(실사고) ────────────────────────────────────────────────
def test_hook_not_duplicated_when_slightly_different():
    """★실사고 재현(07-30 job 9d03ee74): hook과 beats[0]이 따옴표·수식어만 달라도
    예전 완전일치 검사를 빠져나가 훅이 두 번 붙었다."""
    n = '친구가 이거 보더니 "진짜 곱네" 하더라고요'
    h = "친구가 이거 보더니 곱네 하더라고요"
    assert edit_plan._lead_with_hook(n, h) == n


def test_hook_still_prepended_when_genuinely_different():
    """중복만 막는 것이지 훅 얹기 기능 자체를 죽이면 안 된다."""
    out = edit_plan._lead_with_hook("방마다 쿠키가 있어요", "0원으로 집안 냄새 잡는 법")
    assert out.startswith("0원으로 집안 냄새 잡는 법")
    assert "방마다 쿠키가 있어요" in out


def test_hook_identical_is_not_duplicated():
    n = "커피 찌꺼기 그냥 버리지 마세요"
    assert edit_plan._lead_with_hook(n, n) == n


# ── 4. 말투 재생성 게이트 ─────────────────────────────────────────────
def test_tone_gate_threshold_exists():
    assert 0 < edit_plan._TONE_GATE <= 1


def test_cand_tone_reads_beat_narrations():
    """게이트 판정이 실제 비트 나레이션을 읽는가(빈 후보는 0)."""
    good = {"plan": {"beats": [
        {"narration": "방마다 쿠키가 걸려 있는 거 있죠?"},
        {"narration": "홈카페 찌꺼기로 만든 거라지 뭐예요."},
        {"narration": "은은한 향이 퍼지더라구요."}]}}
    flat = {"plan": {"beats": [
        {"narration": "이걸 샀어요."}, {"narration": "좋아요."},
        {"narration": "만족해요."}, {"narration": "추천해요."}]}}
    assert edit_plan._cand_tone(good) > edit_plan._cand_tone(flat)
    assert edit_plan._cand_tone({"plan": {"beats": []}}) == 0.0


def test_generator_accepts_tone_boost():
    """재생성 경로가 부르는 인자가 실제로 존재해야 한다(하네스가 계약을 발명하지 않게)."""
    import inspect
    assert "tone_boost" in inspect.signature(edit_plan._scene_first_candidates).parameters


def test_candidate_quality_joins_beats_as_sentences():
    """★비트를 공백으로 이으면 마침표 없는 후보가 1문장으로 세어져 무조건 통과했다
    (실측 job e9e74aea). 줄바꿈으로 이어 비트 경계를 문장 경계로 만든다."""
    import shopping_shorts.edit_plan as ep
    src = inspect_source(ep._candidate_quality)
    assert '"\\n".join' in src, "비트 join이 줄바꿈이 아니면 어미 다양성이 무력화된다"


def inspect_source(fn):
    import inspect
    return inspect.getsource(fn)
