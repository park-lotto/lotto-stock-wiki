from shopping_shorts.narration_naturalize import normalize_role, naturalize_detail, merge_profile


def _only(stage):
    """해당 스테이지만 켜고 나머지 전부 끈 프로파일(test_naturalize.py의 헬퍼와 동일 패턴)."""
    p = merge_profile({})
    for k, v in p.items():
        if isinstance(v, dict) and "on" in v:
            v["on"] = (k == stage)
    return p


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
    """role은 열린 집합 — 미지는 None + 경고(조용히 넘어가면 결함이 숨는다).

    프로파일은 emotion_arc를 명시적으로 켠 상태(Important5) — `{"naturalness": 0.5}`는
    코드베이스에 없는 유령 노브라 DEFAULT_PROFILE의 우연한 기본값에 의존하는 셈이었다."""
    assert normalize_role("헛소리역할") is None
    d = naturalize_detail("이건 테스트예요", {"emotion_arc": {"on": True, "intensity": 1.0}},
                          beat_role="헛소리역할", beat_index=0, beat_total=3)
    assert any("헛소리역할" in w for w in d["warnings"])


def test_unknown_role_warns_even_with_emotion_arc_off():
    """Critical1: 경고는 감정태그 슬라이더에 종속되면 안 된다.

    emotion_arc.on=False(스테이지 루프가 _tag_for를 아예 안 부름)여도 미지 role 경고는
    나와야 한다 — 그렇지 않으면 "감정태그 끄고 텍스트만 보기" 상태에서 Gemini가 지어낸
    신종 role이 조용히 위치폴백으로 샌다(이 태스크가 없애려던 바로 그 조용함)."""
    p = merge_profile({"emotion_arc": {"on": False, "intensity": 0.0}})
    d = naturalize_detail("이건 테스트예요", p, beat_role="Solution2",
                          beat_index=0, beat_total=3)
    assert any("Solution2" in w for w in d["warnings"])


def test_korean_and_english_role_get_same_tag():
    """같은 역할이면 표기가 달라도 같은 태그 — 작업대와 실제 대본의 role 표기가 다르기 때문.

    Critical2: beat_index=2, beat_total=5는 위치폴백(_ARC_BY_POS[2]==None)과 정본
    (훅→[curious])이 서로 **갈리는** 좌표다 — normalize_role이 항상 None을 반환하도록
    고장나면 두 호출 다 폴백으로 떨어져 태그가 사라지므로 아래 문자열 단언이 실패한다."""
    p = _only("emotion_arc")
    p["emotion_arc"]["intensity"] = 1.0
    ko = naturalize_detail("이거 보세요", p, beat_role="훅",
                           beat_index=2, beat_total=5)["text"]
    en = naturalize_detail("이거 보세요", p, beat_role="hook",
                           beat_index=2, beat_total=5)["text"]
    assert ko == en == "[curious] 이거 보세요"


def test_emotion_arc_tag_table_is_pinned():
    """Important4: 정본 5개 role → 고정 태그. `_ARC_BY_ROLE`을 통째로 갈아엎어도(예:
    curious↔excited를 맞바꿔도) 여기서 잡혀야 한다 — 스위트 전체에 이 표를 직접
    단언하는 테스트가 없었다(hook/cta 두 개만, 값이 아니라 형태만 확인)."""
    p = _only("emotion_arc")
    p["emotion_arc"]["intensity"] = 1.0
    # canon 경로는 beat_index/beat_total과 무관하게 먼저 결정되지만, 위치폴백과
    # 헷갈리지 않는 좌표(2/5 → 폴백 None)를 그대로 써서 혼선 여지를 없앤다.
    def tag(role):
        return naturalize_detail("텍스트", p, beat_role=role, beat_index=2, beat_total=5)["text"]
    assert tag("훅") == "[curious] 텍스트"
    assert tag("페인포인트") == "텍스트"          # 무태그(None)
    assert tag("반전") == "[satisfied] 텍스트"
    assert tag("실용") == "[warm] 텍스트"
    assert tag("CTA") == "[excited] 텍스트"
