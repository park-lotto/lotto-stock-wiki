"""금지어 활용형 탐지 — 오탐 없이 상투어만 잡는가(2026-08-03 실사고).

무슨 일이 있었나: `_banned_phrase_fuzzy_hit`의 need 하한이 2라, 3자 금지어('완벽함')가
**"앞 2자만 같으면 걸림"**이 됐다. 그래서 '완벽해요'·'완벽하게' 같은 **평범한 한국어**가
금지어로 잡혀 `_score_candidate`가 0점 반려했다.
실측(job 6849ebdf1bb1): 심사위원이 최고점(0.733)을 준 후보가 이 오탐 하나로 규칙점수 0이
돼 2등으로 밀렸다 — 추천이 사장님 눈과 어긋나던 원인 중 하나.

★단순히 하한을 올리면 원래 잡던 걸 놓친다('쾌적하게'→'쾌적한'은 공통 앞이 2자뿐이다).
  그래서 **금지어가 활용어인지**로 가른다 — '~하게' 꼴만 어간 매칭을 허용한다.
"""
from shopping_shorts import edit_plan


def _hit(text):
    return edit_plan._banned_phrase_hit([{"narration": text}])


def test_normal_korean_is_not_flagged():
    """★오탐 방지: '완벽해요'는 상투어가 아니라 평범한 말이다."""
    for txt in ("열기 차단도 완벽해요",
                "사생활 보호까지 완벽해요",
                "완벽하게 해결됐어요"):
        assert not _hit(txt), f"평범한 한국어가 금지어로 잡혔다: {txt}"


def test_real_banned_phrases_still_caught():
    """진짜 상투어는 계속 잡아야 한다 — 오탐을 고치려다 탐지를 잃으면 안 된다."""
    for txt in ("이건 정말 완벽함",
                "진짜 신세계네요",
                "동생네서 본 꿀템",
                "고민 해결됐어요",
                "삶의 질 상승했어요"):
        assert _hit(txt), f"금지어를 놓쳤다: {txt}"


def test_conjugated_forms_still_caught():
    """★활용형 탐지는 이 함수의 존재 이유다 — '쾌적하게'→'쾌적한'을 계속 잡아야 한다."""
    for txt in ("쾌적한 공간이 됐어요", "쾌적하게 지내요", "쾌적함이 다르네요"):
        assert _hit(txt), f"활용형을 놓쳤다: {txt}"


def test_unrelated_words_sharing_prefix_are_not_flagged():
    """앞글자만 겹치는 무관한 낱말은 안 잡는다(원래 주석이 경계하던 오탐)."""
    for txt in ("세계 여행 가고 싶어요",      # '신세계' 아님
                "꿀피부 되는 법",             # '꿀템' 아님
                "고민이 많았는데",            # '고민 해결' 아님
                "상승세를 탔어요"):           # '삶의 질 상승' 아님
        assert not _hit(txt), f"무관한 낱말이 잡혔다: {txt}"
