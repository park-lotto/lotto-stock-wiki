"""실용 결론어 강조 — "끝이에요" → "끝!이에요".

사장님 지시(2026-07-17): "실용부분에서 끝이에요를 끝!이에요 이런식으로 강조".
단어 중간에 느낌표를 꽂는 유일한 규칙이라 기존 스테이지(intonation=어절 앞 쉼표,
endings=문장 끝)에 안 맞아 새 스테이지로 뺐다.
"""
import pytest

from shopping_shorts.narration_naturalize import (
    DEFAULT_PROFILE, merge_profile, naturalize_detail,
)


def _run(text, role, profile=None):
    return naturalize_detail(text, merge_profile(profile or {}),
                             beat_role=role, beat_index=0, beat_total=5)["text"]


@pytest.mark.parametrize("src,want", [
    ("뚜껑을 이렇게 딱 돌리면 끝이에요.", "끝!이에요"),
    ("한 번에 완성이에요.", "완성!이에요"),
])
def test_conclusion_word_gets_bang(src, want):
    out = _run(src, "실용")
    assert want in out, f"결론어 강조가 안 됐다: {out!r}"


def test_conclusion_word_gets_bang_formal_tail():
    """'입니다' 꼬리도 강조된다 — 단, 기본 프로파일에서는 직접 관측 불가하다.

    실측(브리프 원 테스트 그대로, 기본 프로파일): `_spoken_style`(intensity=0.4,
    `_conclusion`보다 파이프라인 앞쪽)가 후보 1개짜리 문장에서도 `_take_count`가
    `ceil(1*0.4)=1`이라 **항상** "입니다"→"이에요"를 먼저 바꿔버린다 — "이렇게
    눌러주면 끝입니다."가 `_conclusion`에 도달할 때는 이미 "...끝이에요."라
    "끝!입니다"는 기본 프로파일에서 도달 불가능한 문자열이다(구현이 맞아도 브리프
    원 테스트는 영원히 실패한다 — 스테이지 순서를 바꿔도 같다: `_spoken_style`의
    "입니다" 매치는 앞에 뭐가 붙어있든 무관해 "끝!입니다."도 그대로 "끝!이에요."로
    바뀐다). `_conclusion` 자신의 "입니다" 분기(`_CONCLUSION_TAIL`)를 실제로
    검증하려면 그 앞 스테이지의 변환을 꺼서 격리해야 한다."""
    out = _run("이렇게 눌러주면 끝입니다.", "실용", {"spoken_style": {"on": False}})
    assert "끝!입니다" in out, f"결론어 강조가 안 됐다: {out!r}"


def test_only_on_practical_role():
    """훅·반전의 '끝이에요'까지 건드리지 않는다."""
    out = _run("근데 이건 이걸로 끝이에요.", "반전")
    assert "끝!" not in out, f"실용 아닌 비트에 적용됐다: {out!r}"


def test_is_idempotent():
    """두 번 태워도 '끝!!이에요'가 되면 안 된다."""
    once = _run("돌리면 끝이에요.", "실용")
    twice = naturalize_detail(once, merge_profile({}), beat_role="실용",
                              beat_index=0, beat_total=5)["text"]
    assert "!!" not in twice, f"느낌표가 겹쳤다: {twice!r}"


def test_unrelated_word_untouched():
    """'끝'이 결론어가 아닌 자리(예: '끝나면')엔 안 붙는다 — 과적용 봉인."""
    out = _run("작업이 끝나면 알려드릴게요.", "실용")
    assert "끝!" not in out, f"엉뚱한 '끝'에 붙었다: {out!r}"


def test_knob_can_be_turned_off():
    """words를 비우면 규칙이 꺼진다."""
    out = _run("돌리면 끝이에요.", "실용", {"conclusion": {"words": []}})
    assert "끝!" not in out, f"노브가 안 먹는다: {out!r}"


def test_stage_is_registered():
    """_STAGES에 등록 안 하면 프로파일만 있고 아무 일도 안 일어난다."""
    from shopping_shorts.narration_naturalize import _STAGES
    assert "conclusion" in [name for name, _fn in _STAGES]
    assert "conclusion" in DEFAULT_PROFILE


# ── 구현 검토 중 직접 발견한 충돌(브리프 verbatim 테스트엔 없음) ──
# "끝"/"완성"은 리터럴이라 **더 큰 단어의 뒷부분**일 때도 그대로 걸릴 수 있다
# (Task3가 겪은 클래스와 동일 구조 — "국민가요"/"끝나요"/"하나요"). 두 방향을
# 직접 구성해 확인했다: 동사 어간 충돌은 "끝"/"완성" 둘 다 없음(끝다·완성다라는
# 어간이 한국어에 없다), 명사/접두사 결합 충돌은 있다(아래 두 테스트가 그 증거).


@pytest.mark.parametrize("src", [
    "이 부분이 손끝이에요.",
    "이건 발끝이에요.",
    "여긴 칼끝이에요.",
    "이 뾰족한 데가 붓끝이에요.",
    "여기가 혀끝이에요.",
])
def test_compound_noun_suffix_not_touched(src):
    """'끝'이 합성어 뒷부분(손끝·발끝·칼끝·붓끝·혀끝=신체·도구의 첨단)이면 손대지
    않는다 — 문장 '이건 (뭔가의) 끝(=결론)이다'가 아니라 '이건 N-끝(사물)이다'라
    별개 명사라, 강조하면 "손끝!이에요"처럼 합성어 한가운데 느낌표가 박힌다."""
    out = _run(src, "실용")
    assert "끝!" not in out, f"합성어 뒷부분 '끝'에 잘못 붙었다: {out!r}"


def test_prefix_noun_not_touched():
    """'완성'이 반의 접두사 '미'와 결합한 '미완성'(아직 안 끝남=정반대 의미)이면
    손대지 않는다 — 리터럴 '완성'이 '미완성'의 뒷부분과 표면이 겹쳐, 강조하면
    "미완성!이에요"처럼 '아직 안 끝났다'는 문장 한가운데 '완성' 느낌표가 박혀
    의미가 뒤집힌 것처럼 들린다."""
    out = _run("이건 아직 미완성이에요.", "실용")
    assert "완성!" not in out, f"'미완성'의 뒷부분에 잘못 붙었다: {out!r}"
