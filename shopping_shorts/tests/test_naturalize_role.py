from shopping_shorts.narration_naturalize import normalize_role, naturalize_detail


def test_normalize_role_accepts_korean_english_and_case_variants():
    """실측 17변종(한글·영어·대소문자·동의어)이 정본으로 접힌다."""
    assert normalize_role("훅") == "훅"
    assert normalize_role("hook") == "훅"
    assert normalize_role("Hook") == "훅"
    assert normalize_role("페인포인트") == "페인포인트"
    assert normalize_role("PainPoint") == "페인포인트"
    assert normalize_role("반전") == "반전"
    assert normalize_role("twist") == "반전"
    assert normalize_role("reversal") == "반전"
    assert normalize_role("reveal") == "반전"
    assert normalize_role("실용") == "실용"
    assert normalize_role("utility") == "실용"
    assert normalize_role("practical") == "실용"
    assert normalize_role("Solution") == "실용"
    assert normalize_role("CTA") == "CTA"          # 실측 최다(13회) — 지금은 매칭 실패 중
    assert normalize_role("cta") == "CTA"
    assert normalize_role("  hook  ") == "훅"      # 공백 방어


def test_unknown_role_returns_none_and_warns():
    """role은 열린 집합 — 미지는 None + 경고(조용히 넘어가면 결함이 숨는다)."""
    assert normalize_role("헛소리역할") is None
    d = naturalize_detail("이건 테스트예요", {"naturalness": 0.5},
                          beat_role="헛소리역할", beat_index=0, beat_total=3)
    assert any("헛소리역할" in w for w in d["warnings"])


def test_korean_and_english_role_get_same_tag():
    """같은 역할이면 표기가 달라도 같은 태그 — 작업대와 실제 대본의 role 표기가 다르기 때문."""
    ko = naturalize_detail("이거 보세요", {"naturalness": 1.0}, beat_role="훅",
                           beat_index=0, beat_total=3)["text"]
    en = naturalize_detail("이거 보세요", {"naturalness": 1.0}, beat_role="hook",
                           beat_index=0, beat_total=3)["text"]
    assert ko == en
