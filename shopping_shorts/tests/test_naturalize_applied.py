from shopping_shorts.narration_naturalize import naturalize_detail, normalize_reading


def test_applied_counts_what_actually_happened():
    """적용 횟수가 실제 변경과 일치한다.

    브리프 원안은 {"naturalness": 1.0}을 프로파일로 썼지만 `naturalness`는
    아직 코드에 없는 노브(Task 7 예정)라 여기서 쓰면 DEFAULT_PROFILE의 기본
    강도에 우연히 얹혀 통과할 뿐이다(Task 1 리뷰 Important 지적). 의도가 드러나게
    normalize·emotion_arc만 명시적으로 켠 프로파일로 바꾼다.
    """
    p = {"normalize": {"on": True}, "emotion_arc": {"on": True, "intensity": 1.0}}
    d = naturalize_detail("50% 할인입니다. 지금 확인해보세요.",
                          p, beat_role="CTA", beat_index=0, beat_total=1)
    # Important4 재리뷰: `>= 1`은 카운터가 99를 반환해도 통과하는 죽은 단언이었다.
    # "50% 할인입니다"의 "50%" 1건만 정규화 대상이므로 실제값 2로 고정한다
    # (숫자변환 1 + 기호(%) 변환 1 = normalize_reading이 세는 단위, 아래
    # test_normalize_reading_* 참고).
    assert d["applied"]["normalize"] == 2      # 50% → 오십 퍼센트 (숫자1 + 기호1)
    assert d["applied"]["emotion_arc"] == 1    # CTA → [excited]
    assert "오십 퍼센트" in d["text"]


def test_applied_zero_when_stage_has_nothing_to_do():
    """할 일이 없으면 0 — 이게 '죽은 스테이지'를 드러낸다."""
    p = {"normalize": {"on": True}}
    d = naturalize_detail("그냥 평범한 문장",
                          p, beat_role="훅", beat_index=0, beat_total=1)
    assert d["applied"].get("normalize", 0) == 0   # 숫자·기호 없음


def test_applied_does_not_lie_when_total_tag_cap_removes_our_tag():
    """Important1 재현 케이스 — 캡을 0으로 내리면 태그도 안 붙고 applied도 안 찍혀야 한다.

    수정 전: `_emotion_arc`가 max_tags_per_beat만 스스로 게이트하고
    max_tags_total은 스테이지 루프 밖 `_enforce_total_tag_cap`이 사후 제거했다.
    bump는 이미 찍힌 뒤라 실제로 태그가 안 붙었는데도 applied["emotion_arc"]==1로
    거짓말했다(2026-07-15 재현: text=='음, 지금 확인해보세요.', applied=={'emotion_arc':1}).
    수정 후에는 `_emotion_arc`가 max_tags_total<=0도 미리 게이트해서 애초에 bump가 없다.
    """
    d = naturalize_detail("지금 확인해보세요.", {"caps": {"max_tags_total": 0}},
                          beat_role="CTA", beat_index=0, beat_total=1)
    assert "[excited]" not in d["text"]
    assert d["applied"] == {}                  # emotion_arc 키 자체가 없어야 함(계약: 0=기록없음)
    assert d["text"] == "음, 지금 확인해보세요."   # 태그만 빠지고 나머지 스테이지는 그대로


def test_applied_spoken_style_counts_exact_conversions():
    """배선된 4개 중 하나였던 spoken_style — 정확한 개수를 검증(Important2)."""
    p = {"spoken_style": {"on": True, "intensity": 1.0},
         "fillers": {"on": False}, "emotion_arc": {"on": False}, "endings": {"on": False}}
    d = naturalize_detail("이건 정말 좋습니다. 가격이 저렴합니다.", p)
    assert d["applied"]["spoken_style"] == 2
    assert d["text"] == "이건 정말 좋아요. 가격이 저렴해요."


def test_applied_pronunciation_counts_keys_substituted():
    """정확한 개수를 검증(Important2) — 등장 횟수가 아니라 치환된 키 수."""
    p = {"pronunciation": {"on": True, "dict": {"SNS": "에스엔에스", "AI": "에이아이"}},
         "fillers": {"on": False}, "emotion_arc": {"on": False}}
    d = naturalize_detail("SNS와 AI 그리고 SNS", p)
    assert d["applied"]["pronunciation"] == 2   # SNS가 2번 등장해도 키 수는 2(SNS,AI)
    assert d["text"] == "에스엔에스와 에이아이 그리고 에스엔에스"


def test_applied_pronunciation_ignores_ghost_key_from_chained_replacement():
    """Minor1 재현 — 값↔키가 겹치는 사전에서 유령 매칭을 세지 않는다.

    사전 {"AS센터":"에이에스 센터", "에이에스":"AS"}에서 원문엔 "에이에스"가 없다.
    원문 기준(orig) 판정 전에는 "AS센터"→"에이에스 센터" 치환 후 생겨난 "에이에스"가
    두번째 키에 다시 매칭돼 카운트가 2로 오르고, 텍스트도 "AS 센터"로 도로 뒤집혔다.
    """
    p = {"pronunciation": {"on": True,
                            "dict": {"AS센터": "에이에스 센터", "에이에스": "AS"}},
         "fillers": {"on": False}, "emotion_arc": {"on": False}}
    d = naturalize_detail("AS센터 방문하세요", p)
    assert d["applied"]["pronunciation"] == 1    # 유령 키("에이에스")는 안 셈
    assert d["text"] == "에이에스 센터 방문하세요"  # 유령 치환으로 도로 뒤집히지 않음


def test_applied_phrasing_counts_insertions():
    """정확한 개수를 검증(Important2) — 연결어미마다 쉼표 삽입 횟수."""
    p = {"phrasing": {"on": True, "intensity": 1.0},
         "fillers": {"on": False}, "emotion_arc": {"on": False}}
    d = naturalize_detail("비싸지만 좋은데 사세요", p)
    assert d["applied"]["phrasing"] == 2
    assert d["text"] == "비싸지만, 좋은데, 사세요"


def test_normalize_reading_returns_text_and_count_tuple():
    """Important3 — normalize_reading 직접 호출(Task10 asr_check가 재사용하는 계약)."""
    result = normalize_reading("3.5kg에 2000원")
    assert isinstance(result, tuple) and len(result) == 2
    text, n = result
    assert isinstance(text, str) and isinstance(n, int)
    assert (text, n) == ("삼 점 오 킬로그램에 이천원", 2)


def test_normalize_reading_percent_and_symbol_cases():
    """대표 케이스 — 숫자 단독(%), 숫자+기호(+) 조합."""
    assert normalize_reading("50%") == ("오십 퍼센트", 2)          # 숫자1 + 기호(%)1
    assert normalize_reading("1+1") == ("일 플러스일", 3)          # 숫자2 + 기호(+)1
