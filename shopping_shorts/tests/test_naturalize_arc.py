from shopping_shorts.narration_naturalize import (
    naturalize_detail, _tag_priority, _tag_priority_taggable, _role_tag_rank,
    _TAG_ROLE_PRIORITY, _ARC_BY_ROLE,
)

ROLES = ["훅", "페인포인트", "반전", "실용", "CTA"]


def _p(intensity):
    # whisper off(2026-07-16, Task1 회귀수정): 이 파일은 emotion_arc 하나만 격리해서
    # 보려고 다른 스테이지를 전부 끈다. whisper가 새로 생기며 기본값이 roles=["반전"]이라
    # "반전" role을 쓰는 test_low_intensity_tags_hook_only가 whisper 태그까지 섞여 나와
    # 이 파일의 격리 취지가 깨졌다(whisper는 감정 예산과 무관하게 항상 붙으므로).
    return {"emotion_arc": {"on": True, "intensity": intensity},
            "fillers": {"on": False}, "spoken_style": {"on": False},
            "endings": {"on": False}, "intonation": {"on": False}, "phrasing": {"on": False},
            "whisper": {"on": False}}


def test_tag_priority_puts_hook_and_cta_first():
    """태그 예산이 적으면 훅과 마지막(CTA)부터 — 가장 중요한 자리."""
    assert _tag_priority(5)[:2] == [0, 4]


def test_tagged_beat_count_scales_with_intensity():
    def tagged(intensity):
        return sum(
            naturalize_detail("문장이에요", _p(intensity), beat_role=r,
                              beat_index=i, beat_total=len(ROLES))["applied"].get("emotion_arc", 0)
            for i, r in enumerate(ROLES)
        )
    # 페인포인트는 무태그(설계)라 최대는 4
    assert tagged(0.2) == 1
    assert tagged(0.2) < tagged(0.6) < tagged(1.0)


def test_low_intensity_tags_hook_only():
    hook = naturalize_detail("문장이에요", _p(0.2), beat_role="훅",
                             beat_index=0, beat_total=5)
    mid = naturalize_detail("문장이에요", _p(0.2), beat_role="반전",
                            beat_index=2, beat_total=5)
    assert hook["text"].startswith("[curious]")
    assert mid["text"] == "문장이에요"


def test_max_tags_total_gate_zero_blocks_tagging_and_bump():
    """Task2가 고친 버그 재발 방지: max_tags_total<=0이면 태그도 안 붙고
    applied에도 안 찍혀야 한다(사후 제거만 하고 bump는 이미 찍힌 상태였던 과거 버그)."""
    profile = _p(1.0)
    profile["caps"] = {"max_tags_total": 0, "max_tags_per_beat": 1, "max_fillers_per_text": 2}
    out = naturalize_detail("문장이에요", profile, beat_role="훅", beat_index=0, beat_total=5)
    assert "[curious]" not in out["text"]
    assert out["applied"].get("emotion_arc", 0) == 0


# ---------------------------------------------------------------------------
# I1 재수정: 예산이 태그불가 비트(페인포인트)에 낭비되지 않는지 (2026-07-15 opus 리뷰)
# ---------------------------------------------------------------------------

def _tagged_count(intensity):
    """정본 5비트(훅·페인포인트·반전·실용·CTA)를 각각 독립 호출해 태그 붙은 개수."""
    return sum(
        naturalize_detail("문장이에요", _p(intensity), beat_role=r,
                          beat_index=i, beat_total=len(ROLES))["applied"].get("emotion_arc", 0)
        for i, r in enumerate(ROLES)
    )


def test_role_tag_rank_excludes_painpoint_and_ranks_taggable_roles():
    """페인포인트는 순위가 없다(예산을 소비하지 않음) — 태그 가능한 4개 role만 순위를 갖는다.

    (재리뷰 Important1) 이전엔 마지막 단언이
    `[_role_tag_rank(r) for r in _TAG_ROLE_PRIORITY] == [0, 1, 2, 3]`였다 —
    `_role_tag_rank`는 `_TAG_ROLE_PRIORITY.index(r)`라서 리스트를 자기 자신으로
    인덱싱하는 꼴이라 **순서와 무관하게 항상 [0,1,2,3]**이 나온다. 즉 순서를
    `["실용","반전","CTA","훅"]`으로 뒤섞은 뮤턴트에서도 이 단언은 그대로 통과했고,
    그 뮤턴트에서는 강도 0.3(정본 5비트)일 때 CTA가 태그를 잃는 실제 결함이
    있었는데도 전체 스위트가 초록이었다(재현 확인 완료). 아래 리터럴 고정 +
    블랙박스 검증으로 대체한다."""
    assert _role_tag_rank("페인포인트") is None
    assert _role_tag_rank(None) is None
    assert _role_tag_rank("모르는역할") is None
    # 순서를 리터럴로 고정 — 인덱스 자기참조 항진명제가 아니라 실제 순서를 검증한다.
    assert _TAG_ROLE_PRIORITY == ["훅", "CTA", "반전", "실용"]


def test_role_tag_rank_blackbox_intensity_0_3_tags_hook_and_cta_only():
    """블랙박스 증명 — 내부 랭크 리스트가 아니라 실제 출력으로 검증한다.
    정본 5비트에서 intensity=0.3이면 태그 예산은 `_take_count(4, 0.3)`=2 —
    `_TAG_ROLE_PRIORITY`의 앞 2개(훅, CTA)만 태그를 받아야 한다. `_TAG_ROLE_PRIORITY`
    순서가 뒤섞이는 뮤턴트가 나면 이 결과 집합이 달라져 이 테스트가 죽는다."""
    tagged_roles = set()
    for i, r in enumerate(ROLES):
        out = naturalize_detail("문장이에요", _p(0.3), beat_role=r,
                                beat_index=i, beat_total=len(ROLES))
        if out["applied"].get("emotion_arc", 0):
            tagged_roles.add(r)
    assert tagged_roles == {"훅", "CTA"}


def test_budget_not_wasted_on_painpoint_no_plateau_0_3_to_0_6():
    """I1 핵심 증명 — 정본 5비트에서 강도를 올릴 때 (수정 전엔 0.3~0.6 네 지점이
    문자 단위로 완전히 동일했던) 평지가 줄어든다. 실제 값으로 고정(before: 모두 2)."""
    before_plateau = {0.3: 2, 0.4: 2, 0.5: 2, 0.6: 2}   # 수정 전 실측(리뷰 재현)
    after = {iv: _tagged_count(iv) for iv in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0)}
    assert after == {0.2: 1, 0.3: 2, 0.4: 2, 0.5: 2, 0.6: 3, 0.7: 3, 1.0: 4}
    # 0.6이 더 이상 0.3~0.5와 같지 않다 — 수정 전엔 이 네 지점이 전부 2로 동일했다.
    assert after[0.6] != before_plateau[0.6]
    assert after[0.6] > after[0.5]


def test_painpoint_never_tagged_at_any_intensity():
    """페인포인트는 강도를 최대로 올려도 영구 무태그(설계 계약)."""
    for iv in (0.1, 0.3, 0.5, 0.7, 1.0):
        out = naturalize_detail("문장이에요", _p(iv), beat_role="페인포인트",
                                beat_index=1, beat_total=5)
        assert out["applied"].get("emotion_arc", 0) == 0
        assert "[" not in out["text"]


# ---------------------------------------------------------------------------
# I3: `_tag_priority` 꼬리 순서 커버리지 — 전체 리스트 리터럴 + 위치폴백 경로 고정
# ---------------------------------------------------------------------------

def test_tag_priority_full_order_literal():
    """전체 순서를 리터럴로 고정한다 — 꼬리(`range(1, total-1)`)를 뒤집어도(예:
    [0,4,3,2,1]) 이전엔 아무 테스트도 안 죽었다(리뷰 실측). 전체 리스트 비교로 봉인."""
    assert _tag_priority(5) == [0, 4, 1, 2, 3]
    assert _tag_priority(1) == [0]
    assert _tag_priority(2) == [0, 1]
    assert _tag_priority(3) == [0, 2, 1]


def test_unknown_role_fallback_uses_tag_priority_tail_order():
    """미지 role(위치폴백) 경로에서 꼬리 순서가 실제로 태그 발동을 좌우함을 증명.

    total=5, intensity=0.5 -> n_tagged=3 -> _tag_priority(5)[:3] == [0, 4, 1].
    정순서면 bi=1(문서상 3번째로 채워짐)은 태그되고 bi=3은 안 된다. 꼬리를 뒤집은
    뮤턴트([0,4,3,2,1])라면 정반대(bi=3 태그, bi=1 무태그)가 되어 이 테스트가 죽는다."""
    profile = _p(0.5)
    tagged_bi1 = naturalize_detail("문장이에요", profile, beat_role="미지역할",
                                   beat_index=1, beat_total=5)
    tagged_bi3 = naturalize_detail("문장이에요", profile, beat_role="미지역할",
                                   beat_index=3, beat_total=5)
    assert tagged_bi1["applied"].get("emotion_arc", 0) == 1
    assert tagged_bi3["applied"].get("emotion_arc", 0) == 0


# ---------------------------------------------------------------------------
# I2 재수정: free 모드(미지 role) 위치폴백도 페인포인트와 같은 결함이 있었다 —
# `_tag_priority`의 3번 슬롯(total=5 기준 bi=2)이 `_ARC_BY_POS[2]`=None(무태그)을
# 가리켜, 강도 0.7~0.8에서 예산만 늘고 실제 태그는 늘지 않았다(2026-07-15 재리뷰).
# ---------------------------------------------------------------------------

def _tagged_count_unknown_role(intensity, total=5):
    """미지 role(위치폴백)로 total개 비트를 각각 독립 호출해 태그 붙은 개수."""
    return sum(
        naturalize_detail("문장이에요", _p(intensity), beat_role="미지역할",
                          beat_index=i, beat_total=total)["applied"].get("emotion_arc", 0)
        for i in range(total)
    )


def test_tag_priority_taggable_excludes_untaggable_position():
    """total=5에서 bi=2는 `_ARC_BY_POS[2]`=None이라 태그 불가 — 우선순위에서 빠져야 한다."""
    assert _tag_priority(5) == [0, 4, 1, 2, 3]          # 필터 전(원본) — bi=2 포함
    assert _tag_priority_taggable(5) == [0, 4, 1, 3]     # 필터 후 — bi=2 제거


def test_unknown_role_no_plateau_0_5_to_0_8():
    """I2 핵심 증명 — free 모드(미지 role) 5비트에서 강도 0.5~0.8 구간이 수정 전엔
    문자 단위로 완전히 동일했다(3번 슬롯이 무태그 위치를 가리켜 예산만 소비).
    수정 후 실측값으로 고정한다: 더 이상 네 지점 전부 동일하지 않다."""
    before_plateau = {0.5: 3, 0.6: 3, 0.7: 3, 0.8: 3}   # 수정 전 실측(재리뷰 재현)
    after = {iv: _tagged_count_unknown_role(iv) for iv in (0.5, 0.6, 0.7, 0.8)}
    assert after == {0.5: 3, 0.6: 3, 0.7: 4, 0.8: 4}
    assert after[0.7] != before_plateau[0.7]
    assert after[0.8] != before_plateau[0.8]
    assert after[0.7] > after[0.6]
    # 단조 비감소(같은 값 유지는 허용, 감소는 없어야 함)
    vals = [after[iv] for iv in (0.5, 0.6, 0.7, 0.8)]
    assert vals == sorted(vals)


def test_unknown_role_bi3_now_reachable_at_budget_4():
    """수정 전엔 total=5, n_tagged=4(강도 0.7)에서 bi=3이 태그를 못 받았다 —
    3번 슬롯을 무태그 위치(bi=2)가 차지했기 때문. 필터링 후 bi=3이 태그를 받는다."""
    out = naturalize_detail("문장이에요", _p(0.7), beat_role="미지역할",
                            beat_index=3, beat_total=5)
    assert out["applied"].get("emotion_arc", 0) == 1


# ---------------------------------------------------------------------------
# Minor2: `_TAG_ROLE_PRIORITY` ↔ `_ARC_BY_ROLE` 동기화 불변식 —
# 어긋나면 태그 있는 정본 role이 강도 1.0에서도 영구 무태그로 조용히 죽는다
# (방금 고친 페인포인트 버그의 비의도적 재현).
# ---------------------------------------------------------------------------

def test_tag_role_priority_matches_arc_by_role_taggable_set():
    assert {k for k, v in _ARC_BY_ROLE.items() if v} == set(_TAG_ROLE_PRIORITY)


# ---------------------------------------------------------------------------
# Minor: 브리프 계약 고정 (intensity<=0 게이트 / beat_index 범위이탈 경고)
# ---------------------------------------------------------------------------

def test_zero_or_negative_intensity_always_untagged():
    """intensity<=0 -> 항상 무태그(no-op 게이트지만 브리프 계약이므로 테스트로 고정)."""
    for iv in (0, -0.1, -1.0):
        out = naturalize_detail("문장이에요", _p(iv), beat_role="훅",
                                beat_index=0, beat_total=5)
        assert out["text"] == "문장이에요"
        assert out["applied"].get("emotion_arc", 0) == 0


def test_out_of_range_beat_index_warns():
    """beat_index >= beat_total(배선 오류)이면 경고를 남긴다 — 감정태그가 조용히
    사라지는 실패 모드에 신호를 남기기 위함(Minor)."""
    out = naturalize_detail("문장이에요", _p(1.0), beat_role="미지역할",
                            beat_index=7, beat_total=5)
    assert any("beat_index" in w for w in out["warnings"])
