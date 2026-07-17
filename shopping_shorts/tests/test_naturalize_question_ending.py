"""의문형 어미는 물음표로 — 끝음을 올린다.

사장님 지시(2026-07-17): "의문형은 부호가 없어요 끝을 자연스럽게 올린다".
ElevenLabs는 `?`에서 자연히 끝음을 올린다. 문제는 두 가지였다:
  ① endings가 마침표를 `…`로 바꿔 끝음이 처지는 것(실측: "이거." → "이거…").
  ② 대본이 "?" 없이 의문형으로 끝나는 훅을, `_intonation`의 훅 꼬리 강조 규칙이
     그대로 느낌표로 덮어써버리는 것(실측: "왜 다들 이걸 살까요." →
     "[curious] 왜 다들 이걸, 살까요!").
그래서 규칙은 "?"를 새로 만드는 게 아니라 **의문형 어미인데 "?"가 아닌 것을
"?"로 되돌리는 것**이고(_endings), 그 판정을 `_intonation`의 훅 꼬리 강조
가드와 공유해 두 곳이 각자 판정을 조립하다 드리프트가 나는 걸 막는다(amendment2).

범위는 페인포인트뿐 아니라 훅도 포함한다(amendment1) — 이 코퍼스는 훅도
의문문을 부호 없이 쓰는 게 표준 표기라서다.
"""
import pytest

from shopping_shorts.narration_naturalize import (
    _is_interrogative,
    merge_profile,
    naturalize_detail,
)


def _run(text, role, profile=None):
    return naturalize_detail(text, merge_profile(profile or {}),
                             beat_role=role, beat_index=0, beat_total=5)["text"]


# ── 페인포인트: 브리프 원안 그대로(의문형 어미는 물음표로) ──

@pytest.mark.parametrize("text", [
    "매번 이렇게 다 흘리고 닦기도 귀찮지 않나요.",
    "이거 하나 여는 데 몇 번을 씨름하셨을까요.",
])
def test_painpoint_question_tail_becomes_question_mark(text):
    out = _run(text, "페인포인트")
    assert out.rstrip().endswith("?"), f"끝음이 안 올라간다: {out!r}"
    assert "…" not in out[-3:], f"말줄임이 남아 끝음이 처진다: {out!r}"


def test_painpoint_declarative_is_left_alone():
    """평서문에 물음표를 달면 안 된다 — 과적용 봉인."""
    out = _run("매번 이렇게 다 흘리고 닦기도 귀찮아요.", "페인포인트")
    assert not out.rstrip().endswith("?"), f"평서문에 물음표가 붙었다: {out!r}"


def test_imperative_seyo_is_not_a_question():
    """'해보세요'는 명령형이다 — 물음표를 달면 안 된다."""
    out = _run("한번 열어보세요.", "페인포인트")
    assert not out.rstrip().endswith("?"), f"명령형에 물음표가 붙었다: {out!r}"


def test_existing_question_mark_survives():
    """대본이 이미 '?'로 끝나면 endings가 '…'로 덮어쓰면 안 된다."""
    out = _run("닦기도 귀찮지 않으세요?", "페인포인트")
    assert out.rstrip().endswith("?"), f"물음표가 사라졌다: {out!r}"
    assert "??" not in out, f"물음표가 겹쳤다: {out!r}"


def test_other_roles_untouched():
    """CTA의 의문형까지 건드리지 않는다 — 범위를 페인포인트·훅으로 묶는다."""
    out = _run("이거 보셨나요.", "CTA")
    assert not out.rstrip().endswith("?"), f"CTA에 적용됐다: {out!r}"


# ── 훅: amendment1로 넓힌 범위 ──
# 실측(기본 프로파일, 2026-07-17): 이 세 문장은 전부 "?" 없이 의문형으로 끝나는데
# 고쳐지기 전엔 훅 꼬리 강조 규칙이 그대로 느낌표로 덮어썼다
# ("[curious] 왜 다들 이걸, 살까요!" / "[curious] 이거, 써보셨나요!").

@pytest.mark.parametrize("text", [
    "왜 다들 이걸 살까요.",
    "이거 써보셨나요.",
])
def test_hook_question_tail_becomes_question_mark(text):
    out = _run(text, "훅")
    assert out.rstrip().endswith("?"), f"훅 의문형 끝음이 안 올라간다: {out!r}"
    assert "!" not in out, f"훅 꼬리 강조(느낌표)가 의문형에 잘못 붙었다: {out!r}"
    assert "…" not in out[-3:], f"말줄임이 남아 끝음이 처진다: {out!r}"


def test_hook_declarative_still_gets_exclamation():
    """훅 평서문은 여전히 꼬리 강조(Task2 규칙)를 받는다 — 범위 확장이 이걸 깨면 안 된다."""
    out = _run("장 볼 때마다 정신없이 여기저기 들려있는 이거.", "훅")
    assert out.rstrip().endswith("!"), f"훅 평서문 꼬리 강조가 사라졌다: {out!r}"
    assert not out.rstrip().endswith("?"), f"평서문에 물음표가 붙었다: {out!r}"


# ── amendment2: 공유 감지기 — `_endings`가 안 돌아도 `_intonation` 가드가 독립적으로 막는다 ──

def test_hook_tail_guard_independent_of_endings_stage():
    """`_intonation`의 가드는 `_endings`가 이미 '?'를 박아놨다는 전제에 기대면 안 된다 —
    `_endings`가 꺼져 있어도(intensity 0) 같은 감지기로 독립 판정해야 한다."""
    profile = merge_profile({"endings": {"intensity": 0}})
    out = naturalize_detail("왜 다들 이걸 살까요.", profile,
                             beat_role="훅", beat_index=0, beat_total=5)["text"]
    assert "!" not in out, f"의문형인데 훅 꼬리 강조(느낌표)가 붙었다: {out!r}"


def test_question_conversion_counts_once_not_twice():
    """의문형 블록은 dot/tail 로직보다 먼저 돌아야 한다 — 텍스트는 순서와 무관하게
    맞게 나오지만(재구성이 뒷꼬리 구두점을 항상 버려서), 순서가 뒤바뀌면 dot/tail이
    먼저 "."→"…"로 바꾸고 의문형 블록이 다시 그 자리를 "?"로 바꾸면서 같은 변화를
    두 번 세는 유령 카운트가 생긴다(`ca92f9c8`류 결함과 동일 클래스)."""
    out = naturalize_detail("매번 이렇게 다 흘리고 닦기도 귀찮지 않나요.",
                             merge_profile({}), beat_role="페인포인트",
                             beat_index=0, beat_total=5)
    assert out["applied"].get("endings") == 1, (
        f"의문형 전환 1건인데 endings가 {out['applied'].get('endings')}로 계상됐다: {out!r}"
    )


def test_is_interrogative_detector_direct():
    """공유 감지기 자체의 판정(문서화 겸 회귀 봉인)."""
    assert _is_interrogative("살까요.") is True
    assert _is_interrogative("이미 있어요?") is True
    assert _is_interrogative("좋아요.") is False
    assert _is_interrogative("한번 열어보세요.") is False   # 세요=명령형, 의문형 아님


# ── amendment3: ㄴ가요·ㄹ까요·을까요 죽은 분기를 빼도 실제 커버리지는 그대로 ──

@pytest.mark.parametrize("text", [
    "이거 하나 사야 할까요.",     # 모음어간 + 융합형 ㄹ까요 — "까요"로 커버
    "무거워서 들 수 있을까요.",   # 자음어간 + 을까요 — "까요"만으로도 동일 결과(실측 확인)
])
def test_kkayo_suffix_covers_fused_and_eul_forms(text):
    out = _run(text, "페인포인트")
    assert out.rstrip().endswith("?"), f"끝음이 안 올라간다: {out!r}"
    assert "…" not in out[-3:], f"말줄임이 남아 끝음이 처진다: {out!r}"
