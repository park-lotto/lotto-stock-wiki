"""속삭임 스테이지 — 노브 하나(whisper.roles)의 두 설정값.

전체 role = ASMR 영상 / 일부 role = 강조 도구. 설계 2026-07-16-보이스-속삭임톤-design.md.
검증은 순정 merge_profile({})로 한다 — 격리 프로파일은 emotion_arc를 꺼서 태그 결함을 가린다.
"""
import pytest
from shopping_shorts.narration_naturalize import (
    naturalize_detail, merge_profile, DEFAULT_PROFILE, _STAGES,
)

ROLES = ["훅", "페인포인트", "반전", "실용", "CTA"]


def _d(text, role, bi, profile=None, total=5):
    return naturalize_detail(text, profile, beat_role=role, beat_index=bi, beat_total=total)


def test_default_profile_whispers_only_반전():
    """기본값은 강조 도구 — 반전 비트만 속삭이고 나머지는 안 속삭인다."""
    assert DEFAULT_PROFILE["whisper"] == {"on": True, "roles": ["반전"]}
    got = {r: "[whispers]" in _d("이건 진짜 물건이에요", r, i)["text"]
           for i, r in enumerate(ROLES)}
    assert got == {"훅": False, "페인포인트": False, "반전": True,
                   "실용": False, "CTA": False}


def test_all_roles_makes_asmr():
    """roles에 전체 role을 주면 5비트 전부 속삭임 = ASMR 영상."""
    p = {"whisper": {"on": True, "roles": ROLES}}
    for i, r in enumerate(ROLES):
        assert "[whispers]" in _d("이건 진짜 물건이에요", r, i, p)["text"], r


def test_tag_order_is_emotion_then_whispers():
    """설계 §3.2 — 사장님이 채택한 [curious][whispers] 순서를 문자열로 봉인.

    순서를 바꿔 검증한 적이 없으므로 관측된 순서를 고정한다.
    """
    p = {"whisper": {"on": True, "roles": ["훅"]},
         "caps": {"max_tags_total": 3, "max_tags_per_beat": 2, "max_fillers_per_text": 2}}
    out = _d("진짜 대박이에요", "훅", 1, p)["text"]
    assert out.startswith("[curious][whispers] "), out


def test_whisper_ignores_emotion_budget():
    """설계 §3.1 — whisper는 감정 예산과 별개 축.

    리뷰 지적(Minor, 죽은 단언 수정) — role="실용"·beat_index=3/total=5는 rank
    3 >= n_tagged(기본 intensity 0.3 → 2)라 emotion_arc가 켜져있어도 애초에
    감정태그를 못 받는다. 그래서 옛 버전은 arc ON/OFF 출력이 바이트 단위로
    동일했고(`assert "[warm]" not in out`가 항상 참) 아무것도 검증 못 했다.
    role="훅"(beat_index=0)은 기본 intensity에서 실제로 태그를 받는 자리라
    ON/OFF 차이가 실제로 관측된다 — "arc를 껐더니 감정태그가 사라졌고, 그런데도
    속삭임은 남았다"를 두 눈으로 확인해야 하는 테스트라 두 프로파일을 모두 돈다.
    """
    p_on = {"whisper": {"on": True, "roles": ROLES}, "emotion_arc": {"on": True}}
    p_off = {"whisper": {"on": True, "roles": ROLES}, "emotion_arc": {"on": False}}
    out_on = _d("이건 진짜 물건이에요", "훅", 0, p_on)["text"]
    out_off = _d("이건 진짜 물건이에요", "훅", 0, p_off)["text"]
    assert "[curious]" in out_on     # arc ON: 감정태그가 실제로 붙는다(대조군)
    assert "[curious]" not in out_off  # arc OFF: 감정태그가 사라진다
    assert "[whispers]" in out_on    # 속삭임은 arc 상태와 무관하게 항상 켜져 있다
    assert "[whispers]" in out_off


def test_off_means_no_whisper():
    p = {"whisper": {"on": False, "roles": ROLES}}
    assert "[whispers]" not in _d("이건 진짜 물건이에요", "반전", 2, p)["text"]


def test_empty_roles_means_no_whisper():
    """뮤테이션 앵커 — roles=[]로 만드는 뮤턴트가 반드시 여기서 죽는다."""
    p = {"whisper": {"on": True, "roles": []}}
    assert "[whispers]" not in _d("이건 진짜 물건이에요", "반전", 2, p)["text"]


def test_unknown_role_never_whispers():
    """미지 role(작업대 옛 코퍼스의 body/build)은 속삭이지 않는다.

    emotion_arc는 위치기반으로 폴백하지만 whisper는 폴백하지 않는다 — 속삭임은
    '이 비트가 무슨 역할인가'가 온전히 확정될 때만 켜는 게 맞다(모르면 안 속삭인다).
    """
    p = {"whisper": {"on": True, "roles": ROLES}}
    assert "[whispers]" not in _d("이건 진짜 물건이에요", "body", 1, p)["text"]


def test_applied_counts_whisper():
    """작업대가 '슬라이더 돌렸는데 왜 그대로냐'를 화면에서 보게 하는 계상."""
    p = {"whisper": {"on": True, "roles": ["반전"]}}
    assert _d("이건 진짜 물건이에요", "반전", 2, p)["applied"].get("whisper") == 1
    assert "whisper" not in _d("이건 진짜 물건이에요", "훅", 0, p)["applied"]


def test_per_beat_cap_blocks_second_tag():
    """max_tags_per_beat=1이면 감정태그가 이미 자리를 먹어 속삭임이 안 붙는다."""
    p = {"whisper": {"on": True, "roles": ["훅"]},
         "caps": {"max_tags_total": 3, "max_tags_per_beat": 1, "max_fillers_per_text": 2}}
    out = _d("진짜 대박이에요", "훅", 1, p)["text"]
    assert "[curious]" in out
    assert "[whispers]" not in out


def test_per_beat_cap_block_warns_not_silent():
    """whole-branch 최종 리뷰 Finding6 — 캡이 속삭임을 막으면 경고를 남긴다.

    2026-07-17 실사고("탭 이름이 거짓말이 됐다")가 관측 안 됐던 이유가
    정확히 이거였다 — `_whisper`가 캡에 밀리면 아무 신호 없이 조용히 return했다.
    뮤턴트: `ctx["warnings"].append(...)` 호출을 지우면(캡 억제를 다시 조용하게
    만들면) 이 테스트가 죽는다."""
    p = {"whisper": {"on": True, "roles": ["훅"]},
         "caps": {"max_tags_total": 3, "max_tags_per_beat": 1, "max_fillers_per_text": 2}}
    d = _d("진짜 대박이에요", "훅", 1, p)
    assert "[whispers]" not in d["text"]
    assert any("whisper" in w and "캡" in w for w in d["warnings"]), \
        f"캡 억제가 조용히 사라졌다(경고 없음): {d['warnings']!r}"
    assert not d["applied"].get("whisper"), "억제됐는데 applied에 찍히면 거짓말이다"


def test_cap_not_blocking_whisper_has_no_cap_warning():
    """대조군 — 캡이 실제로 막지 않은 정상 케이스에서는 이 경고가 안 뜬다."""
    p = {"whisper": {"on": True, "roles": ["반전"]}}
    d = _d("이건 진짜 물건이에요", "반전", 2, p)
    assert "[whispers]" in d["text"]
    assert not any("whisper" in w and "캡" in w for w in d["warnings"]), d["warnings"]


def test_whisper_runs_right_after_emotion_arc():
    """스테이지 순서 봉인 — _STAGES 튜플에서 whisper가 emotion_arc 바로 뒤다.

    이 순서가 [감정][whispers]를 만든다. intonation보다 앞이어야 하는 이유도 여기 있다:
    intonation의 lookbehind가 ']'를 제외하므로 태그 뒤 강조어에 유령 쉼표가 안 생긴다.
    """
    names = [n for n, _ in _STAGES]
    assert names.index("whisper") == names.index("emotion_arc") + 1
    assert names.index("whisper") < names.index("intonation")


def test_no_ghost_comma_after_tags():
    """T6 결함의 자매 케이스 — 태그 2개 뒤 강조어에 유령 쉼표가 안 생긴다.

    beat_index=1이 생명줄이다(bi=0이면 추임새 '음, '이 태그와 강조어 사이에 끼어
    lookbehind가 보는 앞글자가 ']'가 아니라 ','가 되어 버그판으로도 재현이 안 된다).
    """
    p = {"whisper": {"on": True, "roles": ["훅"]},
         "caps": {"max_tags_total": 3, "max_tags_per_beat": 2, "max_fillers_per_text": 2}}
    out = _d("진짜 대박이에요", "훅", 1, p)["text"]
    assert "], 진짜" not in out
    assert "[whispers], " not in out


def test_whisper_is_idempotent_on_already_tagged_input():
    """리뷰 지적(Important) — 입력에 이미 [whispers]가 있으면 하나 더 붙이지 않는다.

    재현: 캡 계산이 `1+1=2 > 2`=False라 통과해버려 '[whispers][whispers] ...'가
    만들어졌다(태그 2개짜리 입력은 캡이 막지만 1개짜리는 못 막는다). 이 입력
    shape은 test_naturalize_applied.py의 실제 회귀 케이스와 동일하다(가상의
    걱정이 아니라 이미 스위트가 쓰는 형태). count()로 검증하는 이유는 다른
    기본 스테이지(spoken_style/endings/fillers 등)가 이 문장에 부수효과를
    내더라도 이 테스트의 관심사(중복 여부)와 무관하게 하기 위함이다.
    """
    d = _d("[whispers] 지금 확인해보세요.", "반전", 0, {"emotion_arc": {"on": False}})
    assert d["text"].count("[whispers]") == 1, d["text"]
    # no-op(이미 있었음)이므로 새로 "적용"한 게 아니다 — 안 붙였는데 계상하면
    # T6에서 이미 한 번 고친 거짓말 패턴(찍혔는데 실제로 없음)의 재발이다.
    assert not d["applied"].get("whisper")
