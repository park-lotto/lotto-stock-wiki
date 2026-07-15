import json
from pathlib import Path

from shopping_shorts.narration_naturalize import (
    naturalize_detail, _sentence_starts, _beat_selected, merge_profile, DEFAULT_PROFILE,
)

TWO = "감자 찌지 마세요. 이거 하나면 끝이에요."
_CORPUS_PATH = Path(__file__).resolve().parent.parent / "assets" / "tune_corpus.json"


def _p(intensity, cap=2):
    return {"fillers": {"on": True, "intensity": intensity, "bank": ["음", "아", "그"]},
            "caps": {"max_fillers_per_text": cap, "max_tags_per_beat": 1, "max_tags_total": 3},
            "spoken_style": {"on": False}, "emotion_arc": {"on": False},
            "endings": {"on": False}, "intonation": {"on": False}, "phrasing": {"on": False}}


def test_sentence_starts_finds_each_sentence():
    # 브리프 원안은 [0, 12]였으나 TWO 문자열의 실제 두 번째 문장 시작 오프셋은 11이다
    # (마침표(9)+공백(10) 다음이 "이거"의 '이'(11)). 코드포인트로 직접 검증(off-by-one,
    # 브리프 저작 시점 수기 계산 오류로 판단 — 구현은 브리프 Step3 알고리즘 그대로).
    assert [hex(ord(c)) for c in TWO][:12] == [
        '0xac10', '0xc790', '0x20', '0xcc0c', '0xc9c0', '0x20', '0xb9c8', '0xc138',
        '0xc694', '0x2e', '0x20', '0xc774']
    assert _sentence_starts(TWO) == [0, 11]


def test_filler_count_scales_with_intensity():
    """강도가 오르면 추임새가 실제로 늘어난다(옛 임계형은 항상 1개였다)."""
    low = naturalize_detail(TWO, _p(0.3), beat_index=0, beat_total=1)
    high = naturalize_detail(TWO, _p(1.0), beat_index=0, beat_total=1)
    assert low["applied"]["fillers"] == 1
    assert high["applied"]["fillers"] == 2
    assert low["text"] != high["text"]


def test_low_intensity_skips_some_beats():
    """낮은 강도는 '몇 비트마다 하나' — 모든 비트에 붙지 않는다(도배 방지).

    I1 수정 후에도 이 패턴(0.25 → bi=0,4 선택)은 그대로 보존된다 — 새 게이트
    (`_beat_selected`, bi-1과 비교)가 bi=0을 intensity>0이면 항상 선택하도록
    설계됐고, 그 뒤로는 옛 'every=4' 계산과 우연히 같은 위치(0,4)로 귀결된다.
    옛 역수 양자화 결함은 0.4~1.0 구간의 평지에서 드러났으므로(아래
    test_beat_gate_has_no_plateau_after_fix), 이 테스트는 그대로 회귀 보호로 둔다."""
    p = _p(0.25)   # 새 게이트: floor(bi*0.25) != floor((bi-1)*0.25)
    got = [naturalize_detail(TWO, p, beat_index=i, beat_total=8)["applied"].get("fillers", 0)
           for i in range(8)]
    assert got == [1, 0, 0, 0, 1, 0, 0, 0]


def test_cap_can_limit_below_intensity_derived_count():
    """M5 — 이름을 정직하게 고쳤다. 옛 이름 `..._does_not_kill_intensity`는 C1(캡이
    강도를 죽인다)이 고쳐지기 전엔 사실이 아니었다 — 이 케이스가 단언하는 건
    "cap을 의도적으로 낮게 잡으면(1) 강도가 요구하는 개수(2)보다 실제 적용 수가
    작아질 수 있다"는 정상적인 상한 동작이지, "강도가 살아있다"는 뜻이 아니다.
    강도가 실제로 살아있는지는 test_default_profile_lets_intensity_show_up(C1
    exit proof, cap 미덮어쓰기)이 검증한다."""
    capped = naturalize_detail(TWO, _p(1.0, cap=1), beat_index=0, beat_total=1)
    assert capped["applied"]["fillers"] == 1


# ---------------------------------------------------------------------------
# C1 exit proof — 캡을 덮어쓰지 않은 "진짜 기본 프로파일"에서 강도만 바꾸면
# 결과가 달라야 한다. 수정 전엔 DEFAULT_PROFILE.caps.max_fillers_per_text==1이
# n = min(cap, _take_count(...))에서 항상 병목이 돼 0.3과 1.0이 완전히 동일한
# 문자열을 냈다(2026-07-15 컨트롤러 재현). 이 테스트가 4개 기존 테스트 전부가
# `cap=2`로 유리하게 덮어써서 놓쳤던 사실(보고서 I4)을 직접 고정한다.
# ---------------------------------------------------------------------------

def test_default_profile_lets_intensity_show_up():
    assert DEFAULT_PROFILE["caps"]["max_fillers_per_text"] == 2   # C1 고정값 자체도 pin
    real_line = "감자 찌지 마세요. 집에 있는 이것 하나면 역대급 간식이 탄생합니다."
    p_low = merge_profile({"fillers": {"intensity": 0.3}})
    p_high = merge_profile({"fillers": {"intensity": 1.0}})
    low = naturalize_detail(real_line, p_low, beat_index=0, beat_total=1)
    high = naturalize_detail(real_line, p_high, beat_index=0, beat_total=1)
    assert low["applied"]["fillers"] == 1
    assert high["applied"]["fillers"] == 2
    assert low["text"] != high["text"]


def test_tune_corpus_lines_are_all_single_sentence():
    """I4 — 튜닝 코퍼스(작업대가 실제로 보여주는 10줄)의 한계를 정직하게 고정한다.

    10개 전부 마침표·물음표 등 문장 구분자가 없는 단문장이라 `_sentence_starts`가
    전부 `[0]`을 반환한다 — 즉 지금 코퍼스로는 "문장 수 × 강도" 비례(추임새가
    한 텍스트에 2개 이상 붙는 경우)가 작업대 화면에서 절대 보이지 않는다. 이건
    이 태스크의 결함이 아니라 코퍼스 자체의 구조적 한계다(T8이 코퍼스를 교체하면
    이 테스트도 그때 함께 갱신된다)."""
    lines = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    assert len(lines) == 10
    for line in lines:
        assert _sentence_starts(line["text"]) == [0], line


def test_tune_corpus_lines_still_scale_with_intensity_via_beat_gate():
    """코퍼스 줄은 문장 비례는 못 보여줘도(위 테스트), 비트 빈도 게이트(I1)를 통한
    강도 비례는 여전히 관측 가능하다는 걸 확인한다 — 강도를 올리면 10줄 전체에서
    추임새가 실제로 더 많이 붙는다(줄어들지 않는다)."""
    lines = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    p_low = merge_profile({"fillers": {"intensity": 0.15}})
    p_high = merge_profile({"fillers": {"intensity": 0.9}})
    low_hits = sum(
        naturalize_detail(l["text"], p_low, beat_index=i, beat_total=len(lines))["applied"].get("fillers", 0)
        for i, l in enumerate(lines))
    high_hits = sum(
        naturalize_detail(l["text"], p_high, beat_index=i, beat_total=len(lines))["applied"].get("fillers", 0)
        for i, l in enumerate(lines))
    assert high_hits > low_hits


# ---------------------------------------------------------------------------
# I1 — 비트 빈도 게이트: 역수 양자화 평지 제거 + 단조성.
# ---------------------------------------------------------------------------

def test_beat_gate_has_no_plateau_after_fix():
    """옛 `every = round(1/intensity)`는 0.40~0.65(전부 every=2)·0.70~1.00(전부
    every=1)가 통째로 평지였다(리뷰 실측: 10비트 기준 21개 슬라이더 위치 중 13개가
    단 2칸에 갇힘). 새 게이트는 같은 10비트에서 최대 2칸짜리 겹침만 남는다."""
    counts = []
    for i in range(21):
        intensity = round(i * 0.05, 2)
        counts.append(sum(1 for bi in range(10) if _beat_selected(bi, intensity)))
    assert counts == [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10]
    # 옛 평지 구간(0.40~0.65, 0.70~1.00)에 해당하는 인덱스들이 이제 서로 다른 값을 낸다.
    assert counts[8] != counts[13]     # 0.40 vs 0.65
    assert counts[14] != counts[19]    # 0.70 vs 0.95


def test_beat_gate_selected_count_is_monotonic_nondecreasing():
    """단조성 — 강도를 올리면 발동 비트 수가 절대 줄지 않는다(I1 exit proof)."""
    for beat_total in (1, 5, 8, 10, 13):
        counts = [sum(1 for bi in range(beat_total) if _beat_selected(bi, round(i * 0.05, 2)))
                  for i in range(21)]
        assert all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1)), (beat_total, counts)


def test_beat_gate_always_fires_first_beat_when_intensity_positive():
    """단일 비트 프리뷰(beat_total=1)나 스크립트 맨 첫 비트가 낮은 강도에서 영원히
    스킵되지 않는다 — 순방향(bi+1 vs bi) 비교였다면 bi=0은 intensity==1.0이 아닌
    한 절대 선택되지 못했을 것이다(신규 회귀 방지)."""
    for intensity in (0.01, 0.05, 0.3, 0.5, 0.99, 1.0):
        assert _beat_selected(0, intensity) is True
    assert _beat_selected(0, 0.0) is False


# ---------------------------------------------------------------------------
# I2 — 뱅크 순환: 기본값(intensity=0.2, bank 5종)에서 "음"만 나오던 결함.
# ---------------------------------------------------------------------------

def test_bank_cycles_at_default_intensity_not_stuck_on_first_entry():
    """옛 코드: every=5, bank 5종 → 선택 비트가 {0,5}뿐이라 bank[0%5],bank[0%5]
    (bi로 직접 인덱싱)가 항상 "음","음"이었다. 새 코드는 발동 순번(sel_idx)으로
    인덱싱해 서로 다른 추임새가 나온다."""
    p = merge_profile({})  # 진짜 기본 프로파일(fillers.intensity=0.2, bank 5종)
    seen = []
    for bi in range(10):
        d = naturalize_detail("좋아요", p, beat_index=bi, beat_total=10)
        if d["applied"].get("fillers"):
            seen.append(d["text"].split(",")[0])
    assert len(seen) >= 2                 # 최소 2번은 발동(0.2*10=2)
    assert len(set(seen)) >= 2            # 그리고 서로 다른 추임새가 나온다("음"만이 아님)


# ---------------------------------------------------------------------------
# I3 — 실제 출력 문자열 단언(뮤테이션 킬용) + 결정성.
# ---------------------------------------------------------------------------

def test_fillers_exact_output_two_sentences_order_and_bank_rotation():
    """`filler = bank[(sel_idx + (n - 1 - k)) % len(bank)]` — 이 태스크의 유일한
    비자명 표현식을 실제 출력 문자열로 고정한다. `(n-1-k)`를 `k`로 바꾸거나
    `bank[bi]`로 단순화해도(둘 다 monkeypatch로 재현·확인함, 보고서 참조) 이
    단언이 깨진다."""
    p = {"fillers": {"on": True, "intensity": 1.0, "bank": ["음", "아", "그"]},
         "caps": {"max_fillers_per_text": 2, "max_tags_per_beat": 1, "max_tags_total": 3},
         "spoken_style": {"on": False}, "emotion_arc": {"on": False},
         "endings": {"on": False}, "intonation": {"on": False}, "phrasing": {"on": False}}
    d0 = naturalize_detail(TWO, p, beat_index=0, beat_total=1)
    assert d0["text"] == "음, 감자 찌지 마세요. 아, 이거 하나면 끝이에요."
    assert d0["applied"]["fillers"] == 2
    # 비트가 바뀌면(sel_idx 이동) 같은 문장 구조에서도 뱅크 시작점이 옆으로 밀린다.
    d1 = naturalize_detail(TWO, p, beat_index=1, beat_total=1)
    assert d1["text"] == "아, 감자 찌지 마세요. 그, 이거 하나면 끝이에요."


def test_fillers_deterministic_same_input_same_output():
    """결정성 구속 — `test_naturalize.py`가 다른 스테이지엔 이미 걸어둔 패턴을
    fillers에도 적용한다(이전엔 무테스트였다)."""
    p = _p(0.6)
    a = naturalize_detail(TWO, p, beat_index=2, beat_total=5)
    b = naturalize_detail(TWO, p, beat_index=2, beat_total=5)
    assert a == b


def test_fillers_empty_and_whitespace_text_noop():
    """M4 — `_sentence_starts("")` == `[0]`이라 빈 텍스트에도 추임새를 꽂고
    `_bump`가 찍히던 규약 위반을 막는다(`_bump`는 실제 효과가 났을 때만 찍는다).

    `normalize`(기본 on)는 자기 책임으로 양끝 공백을 지우므로(무관한 부작용),
    이 테스트는 fillers만 켜서 fillers 자체의 규약만 본다."""
    p = _p(1.0)
    p["normalize"] = {"on": False}
    p["pronunciation"] = {"on": False}
    for empty in ("", "   ", "\n"):
        d = naturalize_detail(empty, p, beat_index=0, beat_total=1)
        assert d["text"] == empty
        assert "fillers" not in d["applied"]
