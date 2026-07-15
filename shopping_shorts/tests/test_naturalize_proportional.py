from shopping_shorts.narration_naturalize import (
    naturalize_detail, _take_count, _SPOKEN_MAP, _ENDING_SUFFIXES,
)


def test_take_count_is_proportional_and_ceils():
    """후보 1개짜리 짧은 문장도 낮은 강도에서 반영된다(내림이면 0이라 계단이 된다)."""
    assert _take_count(0, 0.5) == 0
    assert _take_count(1, 0.3) == 1        # 옛 int() 내림이면 0 → 버그였던 지점
    assert _take_count(2, 0.5) == 1
    assert _take_count(2, 1.0) == 2
    assert _take_count(4, 0.5) == 2
    assert _take_count(3, 0.0) == 0


def test_spoken_style_applies_at_low_intensity():
    p = {"spoken_style": {"on": True, "intensity": 0.3}, "fillers": {"on": False},
         "emotion_arc": {"on": False}, "endings": {"on": False}, "intonation": {"on": False}}
    d = naturalize_detail("이거 정말 좋습니다", p, beat_index=0, beat_total=1)
    assert "좋아요" in d["text"]
    assert d["applied"]["spoken_style"] == 1


def test_endings_works_without_period():
    """실제 대본엔 마침표가 있지만 튜닝 코퍼스엔 없다 — 종결어미도 대상이라야 양쪽에서 동작."""
    p = {"endings": {"on": True, "intensity": 1.0}, "fillers": {"on": False},
         "emotion_arc": {"on": False}, "spoken_style": {"on": False}, "intonation": {"on": False}}
    d = naturalize_detail("이거 진짜 좋아요", p, beat_index=0, beat_total=1)
    assert d["text"].endswith("…")
    assert d["applied"]["endings"] == 1


def test_endings_still_converts_periods():
    p = {"endings": {"on": True, "intensity": 1.0}, "fillers": {"on": False},
         "emotion_arc": {"on": False}, "spoken_style": {"on": False}, "intonation": {"on": False}}
    d = naturalize_detail("감자 찌지 마세요. 이거 하나면 끝.", p, beat_index=0, beat_total=1)
    assert "마세요…" in d["text"]


def _endings_only(intensity):
    return {"endings": {"on": True, "intensity": intensity}, "spoken_style": {"on": False},
            "pronunciation": {"on": False}, "phrasing": {"on": False},
            "fillers": {"on": False}, "emotion_arc": {"on": False}, "intonation": {"on": False}}


def test_endings_no_false_positive_on_adverb_and_noun_tails():
    """Critical1 재현 — 옛 `(요|죠|다)(?=\\s|$)`는 부사 '다'와 명사 꼬리 '요'를
    종결어미로 오인했다(2026-07-15 컨트롤러 실측, 기본 강도 0.3에서도 재현).
    강도를 1.0으로 줘도(=오탐이 더 잘 드러나는 조건) 여전히 오탐이 없어야 한다."""
    p = _endings_only(1.0)
    # '다'(부사) 뒤에 `…`가 붙으면 안 된다. 원래 이 단언은 "'돼요'가 목록에 없어
    # 아예 안 잡힌다(false negative)"는 걸 함께 검증하던 것이었는데, Task3 재리뷰
    # N-1로 `돼요`를 `_ENDING_SUFFIXES`에 추가하면서 그 전제가 깨졌다 — 이제
    # '돼요'는 잡혀야 "맞는" 동작이다(파이프라인이 자기가 만든 어미를 자기가 보게
    # 됨). 의도(부사 '다' 오탐 없음)는 유지하되, 진짜 종결어미 '돼요'엔 `…`가
    # 붙는 걸 별도로 확인한다.
    out = naturalize_detail("이거 하나면 다 돼요", p)["text"]
    assert "다…" not in out
    assert out.endswith("돼요…")
    assert "다…" not in naturalize_detail("모두 다 들어있어요", p)["text"]
    assert "중요…" not in naturalize_detail("중요 포인트예요", p)["text"]
    assert "다…" not in naturalize_detail("재료 다 필요 없어요", p)["text"]
    assert "필요…" not in naturalize_detail("재료 다 필요 없어요", p)["text"]


def test_endings_catches_real_script_endings():
    """서버 실측 대본 5줄 — 문장 끝(마침표)이 실제로 `…`를 받는다.

    ⚠️ 이 5줄은 전부 마침표로 끝난다 — 즉 여기서 실증되는 건 **dot 경로**뿐이다
    (Task3 재리뷰 N-2). tail 경로(마침표 없는 대본에서 종결어미로 직접 매칭)는
    이 테스트가 통과해도 전혀 보장되지 않는다 — 목록에서 `거든요`·`라고요`·`니다`·
    `해요`를 지워도 이 테스트는 그대로 통과한다. tail 경로 검증은
    `test_endings_catches_real_script_endings_via_tail_path`와
    `test_endings_tail_path_covers_every_suffix`가 담당한다."""
    p = _endings_only(1.0)
    lines = [
        ("감자 찌지 마세요. 집에 있는 이것 하나면 역대급 간식이 탄생합니다.", "탄생합니다…"),
        ("번거롭게 튀기지 마세요. 기름 한 방울 없어도 밖에서 파는 것보다 훨씬 바삭해지니까요.",
         "바삭해지니까요…"),
        ("아이들 건강 간식은 물론, 남편 맥주 안주로도 이만한 게 없거든요.", "없거든요…"),
        ("속은 쫀득하고 겉은 과자처럼 바삭해요.", "바삭해요…"),
        ("단순히 예쁜 줄만 알았는데 실내 열기는 빨아들이고 공기는 정화해 주더라고요.",
         "주더라고요…"),
    ]
    for src, expect_tail in lines:
        out = naturalize_detail(src, p)["text"]
        assert out.endswith(expect_tail), (src, out)


def test_endings_catches_real_script_endings_via_tail_path():
    """위 테스트와 같은 5줄에서 마침표만 뗀 변형으로 tail 경로를 강제한다
    (Task3 재리뷰 N-2, 리뷰어 제안 그대로 반영) — 이래야 "실대본 테스트"라는
    이름이 실제로 tail 경로에도 해당한다.

    2번째 줄은 제외한다 — 실제 종결부가 `...바삭해지니까요`인데 `_ENDING_SUFFIXES`엔
    `까요`류가 등재돼 있지 않다(등재 어미와 겹치지 않는 실제 누락, false negative —
    `_CONNECTIVES`가 세운 "오탐 0이 더 중요" 원칙상 목록을 함부로 넓히지 않는다).
    그래서 그 줄만 문장 끝 대신, 같은 줄 안의 다른 종결어미(중간의 `마세요`)가
    tail로 걸리는 것으로 대체 검증한다."""
    p = _endings_only(1.0)
    cases = [
        ("감자 찌지 마세요 집에 있는 이것 하나면 역대급 간식이 탄생합니다", "탄생합니다…"),
        ("번거롭게 튀기지 마세요 기름 한 방울 없어도 밖에서 파는 것보다 훨씬 바삭해지니까요",
         "마세요…"),  # 문장 끝(니까요)은 미커버 — 문장 중간 종결어미로 tail 자체를 확인
        ("아이들 건강 간식은 물론, 남편 맥주 안주로도 이만한 게 없거든요", "없거든요…"),
        ("속은 쫀득하고 겉은 과자처럼 바삭해요", "바삭해요…"),
        ("단순히 예쁜 줄만 알았는데 실내 열기는 빨아들이고 공기는 정화해 주더라고요",
         "주더라고요…"),
    ]
    for src, expect_fragment in cases:
        out = naturalize_detail(src, p)["text"]
        assert expect_fragment in out, (src, out)


# _ENDING_SUFFIXES의 각 어미를 tail 경로(마침표 없음)로 최소 1번 실증하는 예문.
# 새 어미를 목록에 추가하면 이 dict에도 예문을 추가해야 커버리지가 유지된다
# (아래 test_endings_tail_path_covers_every_suffix가 누락을 강제로 잡는다).
_TAIL_SAMPLES = {
    "거든요": "아이들 간식으로 이만한 게 없거든요",
    "라고요": "실내 공기가 정화해 주더라고요",
    "세요": "이것부터 꼭 확인하세요",
    "니다": "역대급 간식이 탄생합니다",
    "해요": "겉은 과자처럼 바삭해요",
    "어요": "이거 진짜 하나도 없어요",
    "아요": "이게 훨씬 더 좋아요",
    "에요": "그건 절대 아니에요",
    "예요": "이게 진짜 다예요",
    "네요": "이거 정말 예쁘네요",
    "죠": "그렇죠",
    "돼요": "이 정도면 충분히 돼요",
    "드려요": "제가 알려드려요",
    "져요": "이렇게 하면 훨씬 바삭해져요",
    "데요": "가격도 진짜 좋은데요",
    "봐요": "일단 한번 해 봐요",
}


def test_endings_tail_path_covers_every_suffix():
    """`_ENDING_SUFFIXES`의 어미마다 최소 1번은 tail 경로(마침표 없음)로 `…`를
    받는지 고정한다(Task3 재리뷰 N-2) — 신규 목록 16개 중 다수(거든요·라고요·니다·
    해요·에요·예요·죠 등)가 옛 "실대본 테스트"(전부 마침표로 끝남)로는 전혀
    회귀 보호되지 않았다. `_TAIL_SAMPLES`가 목록과 어긋나면(어미 추가/삭제 시
    예문 갱신을 잊으면) 이 테스트가 먼저 잡는다."""
    missing = set(_ENDING_SUFFIXES) - set(_TAIL_SAMPLES)
    assert not missing, f"_TAIL_SAMPLES에 예문 없는 어미: {missing}"
    p = _endings_only(1.0)
    for suf, text in _TAIL_SAMPLES.items():
        out = naturalize_detail(text, p)["text"]
        assert out.endswith(suf + "…"), (suf, text, out)


def test_spoken_map_rhs_is_subset_of_ending_suffixes():
    """`_spoken_style`이 `_endings`보다 먼저 돌며 종결어미를 새로 만들어낸다
    (됩니다→돼요, 드립니다→드려요 등) — `_endings`가 그 산출물을 인식 못 하면
    파이프라인이 자기가 만든 어미를 자기가 못 보는 결함이 재발한다(Task3 재리뷰
    N-1). `_SPOKEN_MAP`의 모든 우변이 `_ENDING_SUFFIXES` 중 하나로는 끝나야
    한다는 걸 테스트로 강제해, 앞으로 `_SPOKEN_MAP`에 항목을 추가해도 이 결함이
    조용히 재발할 수 없게 한다.

    예외 없음 — `("ㅂ니다", "요")` 항목은 이 결함 때문에 `_SPOKEN_MAP`에서 아예
    삭제했다(우변 `요`가 단음절이라 안전하게 등재할 수 없고, 완성형 한글에선
    리터럴 매칭이 안 되는 죽은 항목이기도 했다 — narration_naturalize.py 주석 참조)."""
    orphans = [(a, b) for a, b in _SPOKEN_MAP
               if not any(b.endswith(suf) for suf in _ENDING_SUFFIXES)]
    assert orphans == [], f"_SPOKEN_MAP 우변이 _ENDING_SUFFIXES 어디에도 안 걸림: {orphans}"


def test_endings_mixed_dot_and_tail_selected_by_position():
    """Important1 — dot 후보와 tail 후보가 섞였을 때 `cands.sort()`가 위치순으로
    고른다(타입별로 뭉쳐 고르지 않는다)는 것을 고정한다. 첫 후보가 tail이고 그
    다음이 dot이라, sort()가 없으면(=dot을 먼저 모아 리스트에 넣던 구코드 순서)
    강도 0.3에서 엉뚱하게 가운데 dot이 먼저 뽑힌다."""
    text = "좋아요 그리고 예뻐요. 진짜 좋아요"
    d03 = naturalize_detail(text, _endings_only(0.3))
    assert d03["text"] == "좋아요… 그리고 예뻐요. 진짜 좋아요"   # 가장 앞(tail)만 선택
    assert d03["applied"]["endings"] == 1
    d06 = naturalize_detail(text, _endings_only(0.6))
    assert d06["text"] == "좋아요… 그리고 예뻐요… 진짜 좋아요"   # 앞의 2개(tail, dot)
    assert d06["applied"]["endings"] == 2


def test_endings_tail_only_proportional():
    """tail 후보만 있는 입력에서 비례 동작(0.3→1곳, 0.6→2곳)을 고정한다 —
    이전엔 tail 비례에 대한 회귀 보호가 전혀 없었다."""
    text = "정말 좋아요 진짜 없어요 완전 좋네요"   # tail 후보 3개(아요/어요/네요)
    d03 = naturalize_detail(text, _endings_only(0.3))
    assert d03["text"] == "정말 좋아요… 진짜 없어요 완전 좋네요"
    assert d03["applied"]["endings"] == 1
    d06 = naturalize_detail(text, _endings_only(0.6))
    assert d06["text"] == "정말 좋아요… 진짜 없어요… 완전 좋네요"
    assert d06["applied"]["endings"] == 2
