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

    emotion_arc를 통째로 꺼도(=감정태그 0개) 속삭임은 그대로 나온다. 이게 깨지면
    'ASMR 톤인데 예산이 모자라 중간 비트가 안 속삭이는' 설계 위반이 된다.
    """
    p = {"whisper": {"on": True, "roles": ROLES}, "emotion_arc": {"on": False}}
    out = _d("이건 진짜 물건이에요", "실용", 3, p)["text"]
    assert "[whispers]" in out
    assert "[warm]" not in out


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
