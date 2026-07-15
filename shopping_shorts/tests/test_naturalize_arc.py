from shopping_shorts.narration_naturalize import (
    naturalize_detail, _tag_priority, _role_tag_rank, _TAG_ROLE_PRIORITY,
)

ROLES = ["훅", "페인포인트", "반전", "실용", "CTA"]


def _p(intensity):
    return {"emotion_arc": {"on": True, "intensity": intensity},
            "fillers": {"on": False}, "spoken_style": {"on": False},
            "endings": {"on": False}, "intonation": {"on": False}, "phrasing": {"on": False}}


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
    """페인포인트는 순위가 없다(예산을 소비하지 않음) — 태그 가능한 4개 role만 순위를 갖는다."""
    assert _role_tag_rank("페인포인트") is None
    assert _role_tag_rank(None) is None
    assert _role_tag_rank("모르는역할") is None
    assert [ _role_tag_rank(r) for r in _TAG_ROLE_PRIORITY ] == [0, 1, 2, 3]


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
