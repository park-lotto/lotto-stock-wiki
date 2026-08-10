from shopping_shorts.narration_naturalize import naturalize_detail, merge_profile


def _p(intensity):
    return {"intonation": {"on": True, "intensity": intensity},
            "fillers": {"on": False}, "spoken_style": {"on": False},
            "endings": {"on": False}, "emotion_arc": {"on": False}, "phrasing": {"on": False}}


def test_intonation_adds_pause_before_trailing_emphasis_word():
    """트레일링 강조어(문장 끝/구두점 앞) 앞엔 짧은 포즈(쉼표)를 넣어 억양을 만든다.

    2026-07-21 사장님 재판정 — 옛 테스트는 "이거 진짜 대박이에요" → "이거, 진짜
    대박이에요"였으나, 그건 intensifier(진짜가 '대박'을 직접 수식)라 실사용에서
    사투리 억양으로 들려 뒤집었다(intensifier는 안 끊는다 →
    test_naturalize_intensifier_v3). 포즈가 살아있는 건 부사가 트레일링일 때뿐이다.
    """
    d = naturalize_detail("가격이 싼데 완전.", _p(1.0), beat_index=0, beat_total=1)
    assert "싼데, 완전" in d["text"], d["text"]
    assert d["applied"]["intonation"] == 1


def test_intonation_intensifier_chain_never_fires():
    """2026-07-21 재판정 — intensifier가 연쇄된 문장(진짜·완전·훨씬이 전부 뒤
    단어를 직접 수식)은 강도와 무관하게 쉼표를 하나도 안 넣는다.

    옛 테스트는 이 문장으로 intensity 스케일링(1개→3개)을 검증했지만, 그 후보들이
    전부 intensifier라 재판정 후엔 후보가 0이 됐다 — 스케일링 자체가 이 문장에선
    성립하지 않는다(_take_count 스케일링은 다른 스테이지 테스트가 커버한다).
    여기서는 "어떤 강도에서도 intensifier는 안 끊는다"를 봉인한다.
    """
    text = "이거 진짜 완전 대박이고 훨씬 좋아요"
    low = naturalize_detail(text, _p(0.3), beat_index=0, beat_total=1)
    high = naturalize_detail(text, _p(1.0), beat_index=0, beat_total=1)
    assert low["text"] == text
    assert high["text"] == text
    assert "intonation" not in low["applied"]
    assert "intonation" not in high["applied"]


def test_intonation_off_is_noop():
    d = naturalize_detail("이거 진짜 대박", _p(0.0), beat_index=0, beat_total=1)
    assert d["text"] == "이거 진짜 대박"


def test_intonation_skips_when_comma_already_there():
    d = naturalize_detail("이거, 진짜 대박", _p(1.0), beat_index=0, beat_total=1)
    assert d["text"] == "이거, 진짜 대박"


def test_intonation_no_false_positive_on_substring_words():
    """오탐 회귀: 강조어 뒤에 경계(공백/구두점/문장끝)가 없으면 매칭 금지.

    "딱"이 "딱딱해요"(강조어 아님)의 앞 두 글자와 겹치는 게 대표 사례
    (브리프가 지적한 함정) — 뒤쪽 lookahead가 없으면 여기서 쉼표가 잘못 박힌다.
    """
    d = naturalize_detail("이거 딱딱해요", _p(1.0), beat_index=0, beat_total=1)
    assert d["text"] == "이거 딱딱해요"
    assert "intonation" not in d["applied"]


def test_intonation_no_false_positive_other_substrings():
    """완전체/절대값/진짜배기 등 강조어를 접두로 포함하는 다른 단어도 오탐하지 않는다.

    "절대값이 커요"(문장 맨 앞에 강조어 접두 단어)는 죽은 프로브였다(Task6 재리뷰
    Minor2) — "절대" 앞에 공백이 없어 lookahead(뒤쪽 경계)를 전혀 시험하지 못하고,
    lookahead가 아예 없는 버그 있는 원안 정규식으로도 애초에 매칭되지 않는다
    (리뷰어 실측: `buggy-pat.finditer('절대값이 커요')` → matches=[]). 앞에 단어를
    붙여 "그 절대값이 커요"로 바꿔 실제로 lookahead를 시험하게 한다.
    """
    for text in ["그 완전체가 좋아요", "그 절대값이 커요", "이건 진짜배기예요"]:
        d = naturalize_detail(text, _p(1.0), beat_index=0, beat_total=1)
        assert d["text"] == text
        assert "intonation" not in d["applied"]


def test_intonation_works_with_default_profile():
    """격리 프로파일(_p)이 아니라 실사용 기본 프로파일(전 스테이지 on)에서도 동작해야
    한다 — 이 프로젝트에서 "격리에선 통과, 실사용에선 무발동"이 반복된 함정이다.

    2026-07-21 재판정 반영 — intensifier "이거 진짜 대박이에요"는 이제 안 끊으므로,
    실제로 포즈가 나는 트레일링 부사 문장으로 검증한다."""
    text = "가격이 싼데 완전."
    p = merge_profile({})
    d = naturalize_detail(text, p, beat_role="실용", beat_index=0, beat_total=1)
    assert d["applied"].get("intonation", 0) >= 1
    assert "싼데, 완전" in d["text"], d["text"]


def test_intonation_no_ghost_candidate_from_emotion_tag():
    """Task6 재리뷰 Important1 회귀 — Task2(보이스) 이후 role=CTA로 이설(2026-07-17).

    `_emotion_arc`가 `_intonation`보다 먼저 돌며 `[curious] ` 같은 v3 태그를 문장
    맨 앞에 붙인다. lookbehind 문자군에 `]`가 빠져 있으면 태그의 닫는 대괄호가
    "앞에 실질 단어가 있다"로 오인돼, 앞에 아무 단어도 없는 태그 바로 뒤 자리에
    유령 포즈(쉼표)가 생긴다(설계 의미 없음) — 게다가 그 유령 포즈가 `applied`에
    "강조 포즈 1건 적용"으로 잘못 계상돼 "실제 효과가 났을 때만 카운트" 규약을
    위배한다. 순정 기본 프로파일(`merge_profile({})`)로 직접 재현·봉인한다.

    ★role=CTA로 바꾼 이유(Task2 보이스 트랙이 새 규칙을 추가한 뒤 재검증) —
    Task2가 `intonation.emphasis_roles=["훅"]` + `_HOOK_TAIL_PAT`(훅 마지막 어절을
    쉼표+느낌표로 강조)를 추가했다. 이 새 규칙은 role=훅에서 **합법적으로**
    `applied["intonation"]`을 1 올린다 — 단, 쉼표는 "태그 바로 뒤"가 아니라
    **훅 마지막 어절 앞**에 박힌다(실측: `'[curious] 진짜, 대박이에요!'` — 쉼표는
    "진짜" 뒤에 있지, "[curious]" 바로 뒤가 아니다). 두 버그가 겉보기까지 완전히
    같지는 않다 — `d["text"].startswith("[curious] 진짜")`는 role=훅에서도 여전히
    참이라(유령 버그였다면 `"[curious], 진짜..."`가 돼 거짓이 됐을 자리) *텍스트*
    단언은 role=훅에 남겨둬도 살아있다. 눈머는 건 오직 `applied["intonation"]`
    **카운터** 단언뿐이다 — 유령 버그와 새 훅꼬리 규칙 둘 다 `intonation`을 1로
    올리므로, role=훅에 남겨두면 "유령이 도졌다"와 "새 규칙이 정상 발동했다"를
    카운터만으로는 구별 못 하는 무력한 판별자가 된다(리뷰 지적 Minor, 2026-07-17 —
    옛 서술은 "겉보기가 똑같다"고 과장했다).

    role=CTA는 `emphasis_roles=["훅"]`에 없으므로 훅꼬리 규칙이 원천적으로
    발동하지 않는다(`ctx.get("role_canon") in (cfg.get("emphasis_roles") or [])`가
    거짓) — 그래서 `intonation`이 조금이라도 찍히면 그 원인은 오직 유령 버그뿐이다.
    실측(정상 코드, `merge_profile({})`, role=CTA, beat_index=1):
    `'[excited] 진짜 대박이에요…'`, `applied={'endings':1,'emotion_arc':1}` —
    `intonation` 없음, 태그 뒤 쉼표 없음. 유령 뮤턴트(lookbehind `\\]` 제거)를
    심으면 버그판 `_EMPHASIS_PAT`가 `'[excited] 진짜...'`에서도 태그 뒤 공백을
    "앞에 실질 단어 있음"으로 오판해 그대로 매치하므로(직접 재현 확인) 이 자리에서도
    유령이 재현되고 `intonation`이 거짓 계상된다 — 즉 CTA는 정상 코드에서 조용하고
    유령 버그에서만 시끄러운, 판별력 있는 자리다.

    ★beat_index=1은 이 리비전에서 판별에 꼭 필요하진 않다(role=CTA는 Task1이 바꾼
    `fillers.roles=["훅"]` 때문에 어느 bi에서도 추임새가 안 낀다 — 실측: bi 0~4
    전부 `'[excited] 진짜 대박이에요…'`로 동일) — 그래도 원 커밋의 값을 그대로
    유지해 회귀 궤적을 보존한다.

    ★격리 프로파일 `_p`로는 이 결함이 안 보이는데, 이유는 **fillers가 아니라
    `emotion_arc`를 끄기 때문**이다 — 태그가 아예 안 붙으니 유령도 없다. 즉
    반드시 기본 프로파일로 검증해야 한다는 이 프로젝트의 반복 교훈이 여기서도
    그대로다.
    """
    p = merge_profile({})
    d = naturalize_detail("진짜 대박이에요", p, beat_role="CTA", beat_index=1, beat_total=5)
    assert d["text"].startswith("[excited] 진짜")  # 태그 바로 뒤엔 쉼표가 없어야 함
    assert "intonation" not in d["applied"]
