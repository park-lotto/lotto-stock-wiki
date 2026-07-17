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
    수정 전 상태로 되돌리면) `않으세요`/`없으세요` 표면형에서 죽는다.

    재재리뷰 Finding A(까요 ㄹ받침 판별자) 정정, 2026-07-17 — 공백 lookbehind에서
    ㄹ받침 판별자로 강화되면서 "까요" 앞 음절은 공백만 없으면 되는 게 아니라
    **ㄹ받침**이어야 한다("이거까요."의 "거"는 ㄹ받침이 아니라 더 이상 안 걸린다).
    그래서 "까요"만 ㄹ받침으로 끝나는 실제 어간("될")에 융합한 형태로 구성한다 —
    "이거 될까요."는 "이 상품이 (내 쓰임에) 맞을까요"라는 실제 의문형이라
    "올리개가 매치하는 모든 표면형을 빠짐없이 돈다"는 이 테스트의 취지(하드코딩
    재발 방지)를 그대로 유지한다(다른 alt는 판별자가 없어 위치와 무관하게
    안전하므로 그대로 공백 유지)."""
    from shopping_shorts.narration_naturalize import (
        _question_tail_match, _QUESTION_GUARD_PAT, _QUESTION_TAIL_ALTS,
    )
    for alt in _QUESTION_TAIL_ALTS:
        t = "이거 될까요." if alt == "까요" else f"이거 {alt}."
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


# ── 재리뷰 지적 Finding1(Critical) — 까요 바레 리터럴이 까다(peel) 평서문을 뒤집는 사고 ──
# 위 나요/가요/하나요 감사에서 던졌던 질문("이 표면형이 명사/평서형과 겹치는가")을
# "까요" 자신에는 안 던졌던 게 재발 원인이었다(이 트랙에서 같은 사고 클래스 4번째).

@pytest.mark.parametrize("text", [
    "귤은 손으로 까요.",
    "마늘은 이렇게 까요.",
    "밤을 하나하나 손으로 까요.",
])
def test_bare_kkayo_declarative_not_flipped(text):
    """`까요`가 이전처럼 위치 무관 바레 리터럴로 남아 있으면 "까다"(껍질을 벗기다,
    쇼핑 콘텐츠 도메인에서 실사용 빈도가 높은 손질 동사)의 해요체 평서형을
    물음표로 뒤집는다(opus 재리뷰 Critical, 이 정정의 근거).
    뮤턴트: `_question_tail_match`의 "까요" 사후검증 블록(ㄹ받침 판별)을 제거하면
    3종 전부 `endswith('?')`로 죽는다."""
    out = _run(text, "페인포인트")
    assert not out.rstrip().endswith("?"), f"평서문이 물음표로 뒤집혔다: {out!r}"


@pytest.mark.parametrize("text", [
    "왜 다들 이걸 살까요.",
    "이게 될까요.",
    "몇 번을 씨름하셨을까요.",
    "이거 하나 사야 할까요.",
    "무거워서 들 수 있을까요.",
    "내일 여기 갈까요.",
])
def test_kkayo_raiser_still_covers_attached_forms(text):
    """`까요` 판별자(앞 음절에 공백 없이 붙어있을 때만 매치)를 추가해도 진짜
    의문형(-ㄹ까요/을까요류) 회수는 그대로 유지돼야 한다 — 전부 어간에 융합된
    형태(연음)라 판별자가 안 막는다.
    뮤턴트: 판별자를 반대로(예: `(?<=\\s)까요`) 뒤집으면 전부 `endswith('?')`
    실패로 죽는다."""
    out = _run(text, "페인포인트")
    assert out.rstrip().endswith("?"), f"끝음이 안 올라간다: {out!r}"
    assert "…" not in out[-3:], f"말줄임이 남아 끝음이 처진다: {out!r}"


def test_kkayo_declarative_guard_still_suppresses_hook_tail():
    """가드(느슨)는 까다 평서문에도 계속 걸려야 한다 — Finding1은 올리개(엄격)만
    좁혔지 가드는 의도적으로 그대로 넓게 둔다(비대칭, 대가는 훅 꼬리 강조 하나뿐).
    `_HOOK_TAIL_PAT`은 이 문장 모양(...손으로 까요.)에 구조적으로 매치하므로,
    가드가 "까요"를 못 잡으면 느낌표가 실제로 붙는다(아래에서 직접 확인).
    뮤턴트: 가드 쪽 "까요"도 올리개처럼 앵커를 걸면(비대칭 무너뜨리기) 이
    테스트가 죽는다."""
    out = _run("장 볼 때마다 밤을 손으로 까요.", "훅")
    assert "!" not in out, f"까다 평서문 훅에 훅 꼬리 강조(느낌표)가 붙었다: {out!r}"


# ── 재재리뷰 지적 Finding A(Critical) — 까요 lookbehind가 명사/부사+'요' 충돌의
# 절반만 닫았던 사고. `까다` 어간 충돌(위 Finding1)은 막았지만, 공백 없이 앞
# 음절에 붙는 명사("까까"=과자)·부사("아까")·의성어("톡")는 lookbehind의
# "공백만 없으면 통과" 조건을 그대로 만족해 여전히 뒤집혔다. ㄹ받침 판별자로
# 클래스 전체를 닫는다.

@pytest.mark.parametrize("text", [
    "이건 그냥 까까요.",
    "우리 애가 좋아하는 까까요.",
    "제가 이거 받은 게 아까요.",
    "껍질을 톡까요.",
])
def test_bare_kkayo_noun_adverb_collision_not_flipped(text):
    """`까요` 앞 음절이 ㄹ받침이 아닌 명사(까까=과자)·부사(아까)·의성어(톡)는
    lookbehind(공백 유무만 확인)만으로는 못 걸러진다 — 전부 공백 없이 한글
    음절이 바로 붙어있어 옛 판별자를 그대로 통과했다(재재리뷰 Finding A 실측).
    뮤턴트: `_question_tail_match`의 ㄹ받침 사후검증을 `(?<=[가-힣])까요` 방식의
    공백-only lookbehind로 되돌리면(1차 정정 상태) 4종 전부 `endswith('?')`로
    죽는다."""
    out = _run(text, "페인포인트")
    assert not out.rstrip().endswith("?"), f"평서문이 물음표로 뒤집혔다: {out!r}"


def test_has_rieul_batchim_predicate_direct():
    """ㄹ받침 판별자 자체의 정확성(문서화 겸 회귀 봉인) — 진짜 의문형 어간의
    마지막 음절은 전부 ㄹ받침(True), 명사·부사·의성어 어근은 전부 ㄹ받침이
    아니다(False). 잔여 'ㄹ'(살살까요의 '살')은 알려진 감수 대상이라 이 직접
    테스트에는 넣지 않는다(위 노출은 end-to-end 케이스로 별도 커버).
    뮤턴트: `% 28 == 8`을 다른 종성 인덱스로 바꾸면(예: `== 4`, ㄴ받침) 아래
    True/False 쌍 전체가 뒤집혀 죽는다."""
    from shopping_shorts.narration_naturalize import _has_rieul_batchim
    for ch in ["살", "될", "할", "갈", "을", "볼", "줄", "팔", "들", "걸"]:
        assert _has_rieul_batchim(ch) is True, f"ㄹ받침인데 False: {ch!r}"
    for ch in ["까", "아", "톡", "만", "쓱", " ", "가"]:
        assert _has_rieul_batchim(ch) is False, f"ㄹ받침 아닌데 True: {ch!r}"


def test_kkayo_raiser_rejects_at_string_start():
    """`까요`가 텍스트 맨 앞이라 앞 음절 자체가 없으면(idx < 0) 판별자가 안전하게
    무효화해야 한다 — 정직한 표기(위생 실측): `idx < 0` 가드를 빼는 뮤턴트를
    직접 심어봤지만 이 테스트를 못 죽인다 — `_QUESTION_TAIL_PAT`이 `$`에
    앵커돼 있어 idx==-1이 나오려면 "까요"가 텍스트 전체의 시작(`m.start(1)==0`)
    이어야 하고, 그 경우 파이썬 음수 인덱싱(`text[-1]`)은 항상 "요"(마지막 음절
    자신, ㄹ받침 아님) 또는 뒷꼬리 그룹(`.`/`…`/공백, 전부 비한글)에만 떨어져
    구조적으로 절대 ㄹ받침에 걸릴 수 없다(=이 가드 제거는 이 파이프라인에서
    등가 뮤턴트다, equivalent mutant). 그래도 가드는 남긴다 — Python 음수
    인덱싱의 우연한 안전성에 기대는 것보다 명시적 방어가 더 읽기 쉽고,
    `_QUESTION_TAIL_PAT`의 앵커 방식이 나중에 바뀌면(예: 다른 위치에서
    `_question_tail_match`를 재사용) 이 불변식이 깨질 수 있다."""
    out = _run("까요.", "페인포인트")
    assert not out.rstrip().endswith("?"), f"문두 '까요'가 물음표로 뒤집혔다: {out!r}"


# ── 재리뷰 지적 Finding2(Important) — 않으세요/없으세요 정책 변경: 올리개에서 제거 ──
# 존댓말 평서·의문은 표기가 원천적으로 동일해 판별자가 없다 — "세요"를 애초에
# 뺀 이유와 같은 클래스. 브랜드스토리 내레이션(장인/사장님 화법)이 실제 코퍼스
# 형태라 감수할 수 없는 사고로 판단, 올리개에서만 뺀다(가드는 유지).

@pytest.mark.parametrize("text,label", [
    ("장인은 기계를 쓰지 않으세요.", "않으세요"),
    ("사장님은 주말에도 쉬는 날이 없으세요.", "없으세요"),
])
def test_seyo_declaratives_not_flipped_by_default(text, label):
    """존댓말 평서형(브랜드스토리 내레이션)이 물음표로 뒤집히면 안 된다.
    뮤턴트: `_QUESTION_TAIL_ALTS`에 `않으세요`/`없으세요`를 다시 넣으면(Finding2
    수정 전 상태) 둘 다 `endswith('?')`로 죽는다."""
    out = _run(text, "페인포인트")
    assert not out.rstrip().endswith("?"), f"{label}: 평서문이 물음표로 뒤집혔다: {out!r}"


def test_annayo_phrasing_still_raises_as_painpoint_substitute():
    """같은 아픈 곳 질문이 `않나요` 표기(브리프 원 코퍼스가 실제로 쓰는 형태)로는
    그대로 살아있다는 걸 봉인한다 — Finding2가 뺀 건 `않으세요` 표기 하나뿐,
    `않나요` 커버리지는 무관해야 한다."""
    out = _run("닦기도 귀찮지 않나요.", "페인포인트")
    assert out.rstrip().endswith("?"), f"끝음이 안 올라간다: {out!r}"


# ── 재리뷰 지적 Finding3(Minor) — 가드 정렬 결정성(위생, 행동엔 영향 없음) ──

def test_guard_alts_ordering_is_fully_deterministic():
    """`_QUESTION_GUARD_ALTS`는 길이 내림차순 + 동길이는 문자열 자체로 완전
    결정적이어야 한다(`key=lambda s: (-len(s), s)`) — 옛 `key=len`은 동길이
    타이를 set 반복순서(PYTHONHASHSEED 의존)에 맡겨 실행마다 컴파일된 패턴
    문자열이 달라질 수 있었다(행동상 무해함은 재리뷰가 576케이스×5시드로 실측
    확인, 이 테스트는 표기 위생만 본다).
    뮤턴트: 소스의 정렬 키를 `key=len, reverse=True`(타이브레이크 없음)로
    되돌리면, 이 테스트가 독립적으로 재계산하는 `(-len(s), s)` 기준 정답과
    비교하므로 실행 프로세스의 set 반복순서가 알파벳 순서와 어긋나는 즉시 죽는다."""
    from shopping_shorts.narration_naturalize import _QUESTION_GUARD_ALTS
    expected = tuple(sorted(set(_QUESTION_GUARD_ALTS), key=lambda s: (-len(s), s)))
    assert _QUESTION_GUARD_ALTS == expected, (
        f"가드 정렬이 (-len, s) 완전결정적 키와 어긋난다: {_QUESTION_GUARD_ALTS!r}"
    )


# ── whole-branch 최종 리뷰 Finding1(Critical) — 있으세요·셨어요 클래스 종결 ──
# 않으세요/없으세요를 "표면형 두 개"로만 닫아놓고 그 표면형이 속한 클래스엔 묻지
# 않았던 게 재발 원인이다(이 트랙 4번째 인스턴스-vs-클래스 사고). 있으세요(존재사
# 어간, 없으세요의 직접 반의어)와 셨어요(과거 존댓말, 명령형이 시제상 불가능한
# 클래스 전체)를 가드에 추가한다.

@pytest.mark.parametrize("text,label", [
    ("혹시 이런 적 있으세요.", "있으세요"),
    ("이거 보셨어요.", "보셨어요"),
])
def test_guard_covers_isseyo_and_syeosseoyo_endings_off(text, label):
    """가드는 `_endings`가 꺼져 있어도(유일한 방어선) `있으세요`/`셨어요`를 억제해야
    한다 — Finding1 수정 전엔 이 표면형이 가드 리터럴에 없어서 `endings.on=False`에서
    훅 꼬리 강조가 그대로 느낌표+쉼표를 덮어썼다.
    뮤턴트: `_QUESTION_GUARD_ALTS`에서 `있으세요`/`셨어요`를 빼면(Finding1 수정 전
    상태) 두 케이스 다 `'!' in out`으로 죽는다."""
    out = _run(text, "훅", {"endings": {"intensity": 0}, "fillers": {"on": False}})
    assert "!" not in out, f"{label}: 의문형인데 훅 꼬리 강조(느낌표)가 붙었다: {out!r}"
    assert not out.rstrip().endswith(","), f"{label}: 의문형 끝에 쉼표가 남았다: {out!r}"


def test_guard_does_not_swallow_bare_seyo_imperative():
    """가드는 바레 `세요`(현재, 동작동사 명령형)까지 넓히지 않는다 — 워크벤치
    코퍼스 0번줄(`끝까지 보세요.`)의 명령형 강조가 그대로 살아있어야 한다.
    뮤턴트: 가드 리터럴에 바레 `세요`를 추가하면(과잉교정) 이 테스트가 죽는다."""
    out = _run("끝까지 보세요.", "훅")
    assert "!" in out, f"명령형 강조가 죽었다: {out!r}"
    assert ", 보세요!" in out, f"명령형 꼬리 강조 형태가 깨졌다: {out!r}"


def test_isseyo_syeosseoyo_are_guard_only_not_raiser():
    """있으세요/셨어요는 **가드 전용** 추가다 — 올리개(`_QUESTION_TAIL_ALTS`)는
    건드리지 않는다(존댓말 평서/의문 표기가 원천적으로 동일해 판별자가 없으므로
    올리개는 이 클래스 전체에서 계속 안전하게 기권한다). 페인포인트에서 물음표로
    뒤집히면 안 된다.
    뮤턴트: `_QUESTION_TAIL_ALTS`에 `있으세요`/`셨어요`를 넣으면(올리개까지 확장,
    범위 초과) 두 케이스 다 `endswith('?')`로 죽는다."""
    for text, label in [("혹시 이런 적 있으세요.", "있으세요"),
                         ("이거 보셨어요.", "보셨어요")]:
        out = _run(text, "페인포인트")
        assert not out.rstrip().endswith("?"), \
            f"{label}: 올리개 범위를 넘어 물음표로 뒤집혔다: {out!r}"
