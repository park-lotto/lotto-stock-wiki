"""훅 마지막 어절 강조 — 쉼표(앞글자 띄우기) + 느낌표(뒤 받치기).

사장님 청취 판정(2026-07-17, 7종 비교): ③ `…들려있는, 이거!`
한글엔 음절 단위 강세 지정 수단이 없어(대문자가 없다) 억양구 구조를 쓴다 —
쉼표로 끊으면 '이거'가 새 억양구의 첫 음절이 돼 피치가 오른다.
"""
from shopping_shorts.narration_naturalize import merge_profile, naturalize_detail


def _run(text, role, profile=None):
    return naturalize_detail(text, merge_profile(profile or {}),
                             beat_role=role, beat_index=0, beat_total=5)["text"]


def test_hook_last_word_gets_comma_and_bang():
    out = _run("요새 해외 인플루언서들 손에 하나씩 들려있는 이거.", "훅")
    assert ", 이거!" in out, f"③ 규칙(쉼표+느낌표)이 적용 안 됐다: {out!r}"


def test_hook_emphasis_does_not_double_comma():
    """대본이 이미 쉼표를 찍어 왔으면 ',, 이거!'가 되면 안 된다."""
    out = _run("요새 다들 쓰는, 이거.", "훅")
    assert ",," not in out and ", , " not in out, f"쉼표가 겹쳤다: {out!r}"
    assert ", 이거!" in out


def test_hook_emphasis_is_idempotent():
    """이미 규칙이 적용된 문장을 다시 태워도 안 망가진다."""
    once = _run("요새 다들 쓰는 이거.", "훅")
    twice = naturalize_detail(once, merge_profile({}), beat_role="훅",
                              beat_index=0, beat_total=5)["text"]
    assert "!!" not in twice, f"느낌표가 겹쳤다: {twice!r}"
    assert ",," not in twice, f"쉼표가 겹쳤다: {twice!r}"


def test_non_hook_roles_untouched_by_tail_emphasis():
    """반전·실용 문장 끝을 느낌표로 바꾸면 톤이 무너진다(속삭임 반전이 '다르더라고요!')."""
    out = _run("근데 이건 완전 다르더라고요.", "반전")
    assert not out.rstrip().endswith("!"), f"훅 아닌 비트에 느낌표가 붙었다: {out!r}"


def test_hook_single_word_sentence_is_left_alone():
    """어절이 하나뿐이면 앞에 끊을 자리가 없다 — ', 이거!'로 시작하면 안 된다."""
    out = _run("이거.", "훅")
    assert not out.lstrip().startswith(","), f"문두에 쉼표가 붙었다: {out!r}"


def test_existing_adverb_emphasis_still_works():
    """기존 intonation(부사 앞 쉼표)을 깨뜨리면 안 된다 — 반대편 봉인."""
    out = _run("이건 진짜 좋아요. 완전 좋아요. 딱 좋아요.", "실용",
               {"intonation": {"intensity": 1.0}})
    assert ", 진짜" in out or ", 완전" in out or ", 딱" in out, \
        f"부사 강조가 죽었다: {out!r}"
