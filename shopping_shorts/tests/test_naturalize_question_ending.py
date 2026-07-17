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


# ── 컨트롤러 오류 정정(2026-07-17): amendment3 "은가요/는가요가 나머지를
# 커버한다"는 결론이 틀렸다 — `건가요`는 `건`으로 시작해 둘 다 못 잡는다.
# Finding 1(가드·올리개 문턱 분리) + Finding 2(ㄴ가요 융합형 표면형 추가) 정정.

@pytest.mark.parametrize("text,label", [
    ("다들 이러고 사는 건가요.", "건가요"),
    ("이거 뭔지 아는 분 계신가요.", "계신가요"),
    ("이거 신상인가요.", "인가요"),
    ("이거 많이 큰가요.", "큰가요"),
])
def test_fused_ngayo_raiser_converts_to_question_mark(text, label):
    """ㄴ가요 융합형(Finding2) — 페인포인트에서 물음표로 올라가야 한다.
    뮤턴트: `_QUESTION_TAIL_PAT`을 옛 목록(4개 신규 표면형 제거)으로 되돌리면
    죽는다 — raiser가 안 걸려 "."가 dot 후보로 남아 "…"가 된다."""
    out = _run(text, "페인포인트")
    assert out.rstrip().endswith("?"), f"{label} 끝음이 안 올라간다: {out!r}"
    assert "…" not in out[-3:], f"{label} 말줄임이 남아 끝음이 처진다: {out!r}"


@pytest.mark.parametrize("text,label", [
    ("다들 이러고 사는 건가요.", "건가요"),
    ("이거 뭔지 아는 분 계신가요.", "계신가요"),
])
def test_fused_ngayo_hook_not_exclaimed(text, label):
    """사장님이 직접 지적한 원 사고 재현 봉인 — ㄴ가요 융합형 훅이 느낌표로
    덮어써지면 안 된다. 두 문턱(guard/raiser) 정정 전체를 한 번에 봉인한다."""
    out = _run(text, "훅")
    assert "!" not in out, f"{label} 훅에 느낌표가 붙었다: {out!r}"


def test_guard_looser_than_raiser_on_plain_gayo_noun():
    """가드(Finding1)는 올리개보다 의도적으로 넓다 — '가요'(歌謠, 명사)로 끝나는
    평서문도 훅 꼬리 억제는 걸리지만(가드가 넓어서), 물음표로는 안 뒤집힌다
    (올리개는 이 자리에 안 걸린다). 뮤턴트: `_is_interrogative`가 `_QUESTION_GUARD_PAT`
    대신 `_question_tail_match`(엄격)를 쓰게 되돌리면 훅 쪽이 죽는다(가드가 더는
    이 자리를 못 잡아 "!" 가 붙는다)."""
    hook_out = _run("이건 최신 가요.", "훅")
    assert "!" not in hook_out, f"명사 '가요'에 훅 꼬리 느낌표가 붙었다: {hook_out!r}"
    pain_out = _run("이건 최신 가요.", "페인포인트")
    assert not pain_out.rstrip().endswith("?"), f"명사 '가요'가 물음표로 뒤집혔다: {pain_out!r}"


def test_gugmingayo_declarative_not_raised_to_question():
    """Finding2 안전성 실측(사장님 지시 원문의 '국민가요' 검토) — 종성산술(b안)이면
    '민'(종성 ㄴ)+'가요' 조합이 물음표로 뒤집힐 위험이 있었다. 명시적 표면형(a안)
    채택으로 이 문장은 걸리지 않는다. 뮤턴트: `_QUESTION_TAIL_PAT`에 b안 스타일
    일반 패턴 `[가-힣]가요$`를 추가하면(=b안을 실제로 심으면) 이 테스트가 죽는다
    (양쪽 role 다 물음표로 뒤집힘) — a안이 구조적으로 안전함을 증명한다."""
    for role in ("훅", "페인포인트"):
        out = _run("이건 국민가요.", role)
        assert not out.rstrip().endswith("?"), \
            f"{role}: 평서문 '국민가요'가 물음표로 뒤집혔다: {out!r}"


def test_strict_raiser_narrower_than_loose_guard_direct():
    """감지기 자체 직접 비교(문서화 겸 회귀 봉인) — 가드는 올리개의 상위집합이어야
    한다: 올리개가 매치하면 가드도 반드시 매치. 역은 성립하지 않는다(가드가 더 넓다).

    리뷰 지적 Finding3 정정(2026-07-17): 옛 코퍼스는 `가요`/`까요` 계열로만 채워져
    있어 "상위집합"이라는 이름을 달고도 그 성질을 실제로 시험하지 않았다 —
    `않으세요`/`없으세요`(올리개엔 있지만 옛 가드 리터럴 `가요|까요|나요`엔 없던
    표면형, Finding2가 잡은 실사고: `건가요!`류와 같은 클래스)가 코퍼스에 빠져
    있었다. `_QUESTION_TAIL_ALTS`에서 코퍼스를 직접 끌어와(하드코딩 재발 방지)
    "올리개가 매치하는 모든 표면형"을 빠짐없이 돈다.
    뮤턴트: `_QUESTION_GUARD_PAT`을 `_QUESTION_TAIL_PAT`과 동일하게(가드=올리개)
    되돌리면 마지막 두 단언(가드만 매치)이 죽는다. `_QUESTION_GUARD_ALTS`에서
    `_QUESTION_TAIL_ALTS`와의 합집합을 빼고 바레 `가요|까요|나요`만 남기면(Finding2
    수정 전 상태로 되돌리면) `않으세요`/`없으세요` 표면형에서 죽는다."""
    from shopping_shorts.narration_naturalize import (
        _question_tail_match, _QUESTION_GUARD_PAT, _QUESTION_TAIL_ALTS,
    )
    for alt in _QUESTION_TAIL_ALTS:
        t = f"이거 {alt}."
        assert _question_tail_match(t) is not None, f"올리개가 안 걸림: {t!r}"
        assert _QUESTION_GUARD_PAT.search(t) is not None, f"가드가 안 걸림(상위집합 위반): {t!r}"
    assert _question_tail_match("이건 최신 가요.") is None, "올리개가 명사 '가요'에 걸리면 안 된다"
    assert _QUESTION_GUARD_PAT.search("이건 최신 가요.") is not None, \
        "가드는 명사 '가요'에도 걸려야 한다(느슨함이 핵심)"


# ── 리뷰 지적 Finding1 — 나요 바레 리터럴이 평서문을 뒤집는 사고 ──

@pytest.mark.parametrize("text", [
    "이 세일 곧 끝나요.",
    "쓸수록 용량이 늘어나요.",
    "내일 여기서 만나요.",
    "아침마다 일찍 일어나요.",
])
def test_bare_nayo_declarative_not_flipped(text):
    """`나요`가 판별 음절 없는 바레 리터럴로 올리개에 남아 있으면 "나"로 끝나는
    어간의 평서형(끝나다·늘어나다·만나다·일어나다 — 쇼핑 내레이션 핵심 어휘)을
    물음표로 뒤집는다(사장님이 직접 지적, 이 정정의 근거).
    뮤턴트: `_QUESTION_TAIL_ALTS`에 바레 `"나요"`를 다시 넣으면(Finding1 수정 전
    상태) 4종 전부 `endswith('?')`로 죽는다."""
    out = _run(text, "페인포인트")
    assert not out.rstrip().endswith("?"), f"평서문이 물음표로 뒤집혔다: {out!r}"


@pytest.mark.parametrize("text", [
    "이거 써보셨나요.",
    "혹시 이런 적 있나요.",
    "이런 거 없나요.",
    "이게 맞나요.",
    "이걸로 되나요.",
])
def test_explicit_nayo_forms_still_raise(text):
    """`나요`를 바레 리터럴에서 명시적 표면형(았/었/였/셨나요·있나요·없나요·되나요·
    맞나요)으로 좁혀도 실제 의문형 커버리지는 유지돼야 한다.
    뮤턴트: `_QUESTION_TAIL_ALTS`에서 이 명시적 표면형들을 빼면(과잉교정) 죽는다."""
    out = _run(text, "페인포인트")
    assert out.rstrip().endswith("?"), f"끝음이 안 올라간다: {out!r}"


# ── 리뷰 지적 Finding2 — 가드가 올리개의 진짜 상위집합이 아니었던 사고 ──

@pytest.mark.parametrize("text,label", [
    ("닦기도 귀찮지 않으세요.", "않으세요"),
    ("이런 거 없으세요.", "없으세요"),
])
def test_guard_covers_seyo_forms_endings_off(text, label):
    """가드는 `_endings`가 꺼져 있어도(유일한 방어선) `않으세요`/`없으세요`를
    억제해야 한다 — 옛 가드 리터럴(`가요|까요|나요`)엔 이 표면형이 없어서
    `endings.on=False`에서 훅 꼬리 강조가 그대로 느낌표+쉼표를 덮어썼다
    (`[curious] 닦기도 귀찮지, 않으세요!`).
    뮤턴트: `_QUESTION_GUARD_ALTS`를 옛 바레 리터럴(`가요|까요|나요`)만으로
    되돌리면 두 케이스 다 `'!' in out`으로 죽는다."""
    out = _run(text, "훅", {"endings": {"intensity": 0}, "fillers": {"on": False}})
    assert "!" not in out, f"{label}: 의문형인데 훅 꼬리 강조(느낌표)가 붙었다: {out!r}"
    assert not out.rstrip().endswith(","), f"{label}: 의문형 끝에 쉼표가 남았다: {out!r}"
