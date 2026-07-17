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
    # N-4(갱신 2026-07-17 Task1): 원래 이 자리엔 "fillers가 이미 텍스트를 바꾼다
    # ('음, ' 삽입)"는 주석이 있었으나 지금은 틀린 서술이다 — Task1이 fillers에
    # 역할 게이트를 추가했고(기본 roles=["훅"]) 이 테스트의 beat_role은 "CTA"라
    # 애초에 fillers가 발동하지 않는다(뱅크도 "음"에서 감탄사류로 교체됨). 그래도
    # 이 assert 자체의 취지("emotion_arc가 거짓 카운트를 안 남긴다")는 그대로 유효하다.
    assert "emotion_arc" not in d["applied"]    # emotion_arc 키 자체가 없어야 함(계약: 0=기록없음)
    # Task 3: endings가 기본 강도(0.3)에서도 마침표 1개를 …로 바꾸도록 배선됐다
    # (이전엔 내림 계산이라 후보 1개면 0.3에서 무발동인 죽은 스테이지였다).
    # 필러 접두사가 사라진 이유는 위 N-4 갱신 설명 참조(역할 게이트, CTA≠훅).
    assert d["text"] == "지금 확인해보세요…"   # 태그·필러 다 빠지고 endings만 적용됨


def test_emotion_arc_tag_survives_total_cap_when_input_has_existing_tag():
    """N-3 — I-1의 하중 지지 불변식을 직접 pin한다.

    `_emotion_arc`의 max_tags_total 게이트는 `_enforce_total_tag_cap`의 "앞에서
    cap개 보존" 규칙을 전제로 "우리 태그(항상 0번째)는 cap>=1이면 절대 안 지워진다"고
    가정한다. 기존 테스트는 max_tags_total=0(전부 제거)만 다뤄서 이 가정 자체는
    무테스트였다 — `_enforce_total_tag_cap`이 "뒤에서 cap개 보존"으로 바뀌면 이
    가정이 조용히 깨지고 거짓말(태그는 지워졌는데 applied는 찍힘)이 부활한다.
    입력에 이미 다른 태그([whispers])가 있는 채로 cap=1을 줘서, 우리 태그가 그
    기존 태그를 밀어내고 생존하는지 + applied 카운트가 그 생존과 일치하는지를
    같이 확인한다."""
    p = {"normalize": {"on": False}, "spoken_style": {"on": False},
         "pronunciation": {"on": False}, "phrasing": {"on": False},
         "endings": {"on": False}, "fillers": {"on": False},
         "emotion_arc": {"on": True, "intensity": 1.0}, "intonation": {"on": False},
         "caps": {"max_tags_total": 1}}
    d = naturalize_detail("[whispers] 지금 확인해보세요.", p,
                          beat_role="CTA", beat_index=0, beat_total=1)
    assert "[excited]" in d["text"]
    assert d["applied"]["emotion_arc"] == 1


def test_applied_whisper_does_not_lie_when_total_tag_cap_removes_it():
    """whole-branch 최종 리뷰 Finding2(Minor, 2026-07-17) 재현 — `_enforce_total_tag_cap`이
    `max_tags_total`로 whisper 태그를 사후에 지워도 applied는 'whisper: 1'로
    거짓 계상됐다(`ca92f9c8` 계약 "실제 효과만 센다" 위반). `_emotion_arc`(항상
    태그 목록 0번째)는 이 캡에 절대 안 걸리지만(자기 게이트가 `max_tags_total<=0`을
    미리 본다), `_whisper`(항상 1번째)는 자신의 게이트(`max_tags_per_beat`)와
    이 캡(`max_tags_total`)이 서로 다른 노브라 못 막는다 — 실측(`max_tags_total=1`,
    `max_tags_per_beat` 기본값 2): 텍스트='[curious]진짜, 대박이에요!'인데
    applied=={'whisper': 1}.
    뮤턴트: `naturalize_detail`의 사후 보정(`ctx["applied"].pop("whisper", ...)`)을
    지우면 태그가 안 남았는데 applied["whisper"]==1로 죽는다."""
    p = {"normalize": {"on": False}, "spoken_style": {"on": False},
         "pronunciation": {"on": False}, "phrasing": {"on": False},
         "endings": {"on": False}, "fillers": {"on": False},
         "emotion_arc": {"on": True, "intensity": 1.0},
         "whisper": {"on": True, "roles": ["반전"]},
         "intonation": {"on": False},
         "caps": {"max_tags_total": 1, "max_tags_per_beat": 2}}
    d = naturalize_detail("지금 확인해보세요.", p,
                          beat_role="반전", beat_index=0, beat_total=1)
    assert "[whispers]" not in d["text"], f"캡이 못 지웠다(테스트 전제 확인 실패): {d['text']!r}"
    assert "[satisfied]" in d["text"]
    assert "whisper" not in d["applied"], f"태그가 지워졌는데 applied가 거짓말: {d['applied']!r}"
    assert d["applied"]["emotion_arc"] == 1


def test_total_tag_cap_strip_inserts_missing_space():
    """whole-branch 최종 리뷰 Finding2 부수 사고 — `_enforce_total_tag_cap`이 뒤쪽
    태그를 지우면, 태그끼리는 원래 공백이 없어서(`_whisper`가 `[감정][whispers] 본문`
    형태로 붙인다) 살아남은 태그가 본문에 바로 붙어버린다
    ('[curious]진짜, 대박이에요!'처럼 — 실측). 잘라낸 자리에 공백 하나를 보충한다.
    뮤턴트: 공백 보충 분기(`kept += " "`)를 지우면 태그-본문 경계 공백이 사라져 죽는다."""
    from shopping_shorts.narration_naturalize import _enforce_total_tag_cap
    out = _enforce_total_tag_cap("[curious][whispers] 진짜, 대박이에요!", 1)
    assert out == "[curious] 진짜, 대박이에요!", f"태그-본문 경계 공백이 안 채워졌다: {out!r}"


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


def test_applied_pronunciation_counts_one_for_overlapping_key_pair():
    """N-1 재현 — 겹침 사전({"AI칩","AI"} 류, 발음사전의 표준 사용법)에서 긴 키가
    먼저 통째로 치환되면 원문(orig)엔 "AI"가 있어 게이트는 통과하지만, 지금
    `text`엔 이미 "AI"라는 부분문자열이 없어 실제로는 no-op이어야 한다.
    게이트만 보고 세면(직전 수정의 하이브리드 버그) 2로 거짓말 났었다 — 실효과만
    세면 1이어야 한다."""
    p = {"pronunciation": {"on": True,
                            "dict": {"AI칩": "에이아이 칩", "AI": "에이아이"}},
         "fillers": {"on": False}, "emotion_arc": {"on": False}}
    d = naturalize_detail("AI칩 사세요", p)
    assert d["applied"]["pronunciation"] == 1
    # Task 3: endings(기본 on)가 마침표 없는 "사세요"도 종결어미 후보로 잡아 문미에
    # …를 붙인다(이전엔 마침표 전용이라 무발동인 죽은 스테이지였다).
    assert d["text"] == "에이아이 칩 사세요…"


def test_pronunciation_dict_is_single_pass_no_chaining():
    """N-2 계약 pin — {"A":"B","B":"C"} + "A"는 체이닝(→"C")되지 않고 1패스만
    적용돼 "B"에서 멈춘다. `orig`가 원문으로 고정되므로 첫 치환의 결과("B")는
    두번째 키("B")의 판정 대상(orig="A")에 없어 재적용되지 않는다. 이 계약이
    테스트로 안 박혀 있으면 나중에 `orig`를 `text`로 되돌려도(연쇄 부활) 전부
    그린으로 통과한다."""
    p = {"pronunciation": {"on": True, "dict": {"A": "B", "B": "C"}},
         "fillers": {"on": False}, "emotion_arc": {"on": False}}
    d = naturalize_detail("A", p)
    assert d["text"] == "B"                       # 체이닝 없음(1패스)
    assert d["applied"]["pronunciation"] == 1


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
    # Task 3: endings(기본 on)가 마침표 없는 "방문하세요"도 종결어미 후보로 잡아
    # 문미에 …를 붙인다(이전엔 마침표 전용이라 무발동인 죽은 스테이지였다).
    assert d["text"] == "에이에스 센터 방문하세요…"  # 유령 치환으로 도로 뒤집히지 않음


def test_applied_phrasing_counts_insertions():
    """정확한 개수를 검증(Important2) — 연결어미마다 쉼표 삽입 횟수."""
    p = {"phrasing": {"on": True, "intensity": 1.0},
         "fillers": {"on": False}, "emotion_arc": {"on": False}}
    d = naturalize_detail("비싸지만 좋은데 사세요", p)
    assert d["applied"]["phrasing"] == 2
    # Task 3: endings(기본 on)가 마침표 없는 "사세요"도 종결어미 후보로 잡아
    # 문미에 …를 붙인다(이전엔 마침표 전용이라 무발동인 죽은 스테이지였다).
    assert d["text"] == "비싸지만, 좋은데, 사세요…"


def test_normalize_reading_returns_text_and_count_tuple():
    """Important3 — normalize_reading 직접 호출(Task10 asr_check가 재사용하는 계약)."""
    result = normalize_reading("3.5kg에 2000원")
    assert isinstance(result, tuple) and len(result) == 2
    text, n = result
    assert isinstance(text, str) and isinstance(n, int)
    assert (text, n) == ("삼 점 오 킬로그램에 이천원", 2)


def test_normalize_reading_percent_and_symbol_cases():
    """대표 케이스 — 숫자 단독(%), 숫자+기호(+) 조합.

    N-5: 기호 치환을 앞뒤 공백으로 바꿔 뒷 단어가 안 붙게 했다("일 플러스일" →
    "일 플러스 일"). 기존 "일 플러스일"은 결함을 정답으로 못박은 값이었다."""
    assert normalize_reading("50%") == ("오십 퍼센트", 2)          # 숫자1 + 기호(%)1
    assert normalize_reading("1+1") == ("일 플러스 일", 3)         # 숫자2 + 기호(+)1
