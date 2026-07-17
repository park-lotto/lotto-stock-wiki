"""추임새 규칙 v2 — 감탄·놀람만, 훅에만, 대본을 덮어쓰지 않는다.

★2026-07-17 실측(라이브 경로 synthesize_line, 미나 1.6)으로 드러난 것:
대본에 "와, 요새…"라고 써넣었는데 엔진이 그 앞에 "[curious] 음,"을 또 붙여
**"음, 와, 요새…"**가 됐다. 사장님이 "실제 대본 넣으니 억양이 부자연스럽다"고
한 것의 정체다. fillers가 대본을 덮어쓴 것.

사장님 판정: "음~ 이런건 빼고 앞에 들어가는 추임새는 감탄 놀람 이런 추임새로
해야해. 저런건 의미없어."
"""
import pytest

from shopping_shorts.narration_naturalize import (
    DEFAULT_PROFILE, merge_profile, naturalize_detail,
)


def _run(text, role, profile=None, bi=0, bt=5):
    """기본 프로파일 경로로 돌린다 — 격리 프로파일은 기본값의 결함을 숨긴다.

    ★계획서 원문 버그 수정(2026-07-17 구현 중 발견): naturalize_detail은
    {"text","applied","warnings"} dict를 반환하는데, 계획서 원문은 이 dict를
    그대로 반환해 호출부(.lstrip() 등 문자열 메서드)가 전부 AttributeError로
    죽었다. ["text"]로 언랩하는 한 줄만 고친다 — 다른 로직은 손대지 않는다.
    """
    return naturalize_detail(text, merge_profile(profile or {}),
                             beat_role=role, beat_index=bi, beat_total=bt)["text"]


def test_bank_has_no_hesitation_fillers():
    """머뭇거림('음','아','그','뭐','자')은 뱅크에서 사라져야 한다 — 사장님이 기각."""
    bank = DEFAULT_PROFILE["fillers"]["bank"]
    for w in ("음", "아", "그", "뭐", "자"):
        assert w not in bank, f"머뭇거림 '{w}'가 아직 뱅크에 있다: {bank}"
    assert bank, "뱅크가 비면 추임새 기능 자체가 죽는다"


def test_bank_is_exclamation_type():
    """감탄·놀람류만 남는다."""
    assert set(DEFAULT_PROFILE["fillers"]["bank"]) <= {"와", "오", "우와", "헐", "이야"}


def test_filler_only_on_hook_role():
    """훅에만 붙는다 — 반전이 '헐, 근데 이건…'이 되면 안 된다."""
    for role in ("페인포인트", "반전", "실용", "CTA"):
        out = _run("근데 이건 진짜 다르더라고요.", role)
        for w in DEFAULT_PROFILE["fillers"]["bank"]:
            assert not out.lstrip().startswith(w + ","), \
                f"{role}에 추임새가 붙었다: {out!r}"


def test_filler_does_appear_on_hook():
    """반대편 봉인 — 역할 게이트가 과해서 훅에서도 안 나오면 기능이 죽은 것."""
    out = _run("요새 다들 쓰는 이거.", "훅",
               {"fillers": {"intensity": 1.0}})
    bank = DEFAULT_PROFILE["fillers"]["bank"]
    assert any(out.lstrip().startswith(w + ",") or f"] {w}," in out for w in bank), \
        f"훅에 추임새가 안 붙었다: {out!r}"


@pytest.mark.parametrize("already", ["와, 요새 다들 쓰는 이거.",
                                     "헐, 이거 보셨어요.",
                                     "음, 요새 다들 쓰는 이거."])
def test_does_not_stack_on_script_that_already_has_one(already):
    """★대본에 이미 추임새가 있으면 손대지 않는다 — '음, 와,' 사고 재발 방지.

    옛 뱅크의 '음'도 막는다: 사장님이 옛 대본을 그대로 넣을 수 있다.
    """
    out = _run(already, "훅", {"fillers": {"intensity": 1.0}})
    body = out.split("]")[-1].strip() if "]" in out else out.strip()
    first_word = body.split(",")[0].strip()
    assert body.startswith(first_word + ","), f"형태가 깨졌다: {out!r}"
    # 추임새가 두 개 연달아 나오면 안 된다
    assert not any(body.startswith(f"{w}, {v},")
                   for w in ("와", "오", "우와", "헐", "이야", "음", "아", "그", "뭐", "자")
                   for v in ("와", "오", "우와", "헐", "이야", "음", "아", "그", "뭐", "자")), \
        f"추임새가 겹쳐 붙었다: {out!r}"


def test_roles_absent_means_all_beats():
    """저장된 옛 프리셋엔 roles 키가 없다 — 없으면 옛 동작(전 비트)을 유지한다.

    없는 키를 '아무 비트도 아님'으로 읽으면 기존 프리셋의 추임새가 통째로 사라진다.
    실패 방향을 '보이는 쪽'으로 잡는다.

    ★계획서 원문 버그(2026-07-17 구현 중 발견, 단순 오탈자가 아니라 구조적 문제):
    원문은 `merge_profile({...})`로 이미 병합된 dict에서 `.pop("roles")`한 뒤 그걸
    다시 `naturalize_detail(...)`에 넘긴다. 그런데 `naturalize_detail`은 내부에서
    `merge_profile(profile)`을 **다시** 호출하고, `merge_profile`은 매번
    `deepcopy(DEFAULT_PROFILE)`에서 시작해 넘겨받은 dict의 키만 얕게 덮어쓴다
    (`dict.update`, 키를 지우는 연산이 아니다) — 그래서 pop으로 지운 "roles"는
    재병합 시 DEFAULT_PROFILE의 `["훅"]`으로 되살아난다(실측 확인 완료).
    이중 병합 여부와 무관하게 더 근본적인 문제가 있다: DEFAULT_PROFILE이 이제
    fillers.roles의 기본값을 갖는 한, "roles 키가 아예 없는 raw dict"를
    `naturalize_detail`에 최초 1회만 통과시켜도 결과는 똑같다 — merge_profile은
    "키가 없으면 기본값으로 채운다"이지 "명시적으로 None을 유지한다"가 아니기
    때문이다(실측: raw `{"fillers": {...bank 등...}}`(roles 키 자체가 없음)을
    `naturalize_detail`에 바로 넘겨도 결과 roles는 여전히 ["훅"]).
    즉 **디스크에 저장된 진짜 옛 프리셋(roles 키가 원래 없던 파일)은 공개 API
    경로로는 이 폴백에 절대 도달하지 못한다** — 조용히 "훅만" 동작으로 바뀐다.
    roles=None을 실제로 관철하는 유일한 방법은 `{"fillers": {"roles": None}}`처럼
    **명시적으로 None을 지정**하는 것뿐이다(dict.update는 present 키의 값이 None이어도
    그대로 덮어쓴다). 이건 merge_profile의 기존 설계(재귀 병합이 아닌 얕은 병합)의
    산물이고 Task 1 범위(DEFAULT_PROFILE·_fillers)를 벗어나므로 여기서 고치지 않는다
    — 대신 `_fillers` 내부 로직 자체(계획서 Step 3, `roles = cfg.get("roles")`)를
    직접 검증하도록 이 테스트만 private 스테이지 함수를 raw cfg로 호출하게 바꾼다.
    이게 계획서 Step 5 뮤턴트#3("roles = cfg.get('roles') or []")이 실제로 겨냥하는
    코드이기도 하다.
    """
    from shopping_shorts.narration_naturalize import _fillers
    cfg = {"on": True, "intensity": 1.0,
           "bank": ["와", "오", "우와", "헐", "이야"]}   # roles 키 자체가 없음
    ctx = {"beat_index": 0, "beat_total": 5, "role_canon": "반전",
           "caps": {"max_fillers_per_text": 2}, "applied": {}}
    out = _fillers("근데 이건 다르더라고요.", cfg, ctx)
    bank = cfg["bank"]
    assert any(w + "," in out for w in bank), f"roles 없는 프리셋에서 추임새가 죽었다: {out!r}"
