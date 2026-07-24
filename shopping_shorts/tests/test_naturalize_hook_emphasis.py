"""훅 마지막 어절 강조 — 쉼표(앞글자 띄우기) + 느낌표(뒤 받치기).

사장님 청취 판정(2026-07-17, 7종 비교): ③ `…들려있는, 이거!`
한글엔 음절 단위 강세 지정 수단이 없어(대문자가 없다) 억양구 구조를 쓴다 —
쉼표로 끊으면 '이거'가 새 억양구의 첫 음절이 돼 피치가 오른다.
"""
from shopping_shorts.narration_naturalize import merge_profile, naturalize_detail, _LEADING_TAGS_PAT


def _run(text, role, profile=None):
    return naturalize_detail(text, merge_profile(profile or {}),
                             beat_role=role, beat_index=0, beat_total=5)["text"]


def _run_detail(text, role, profile=None, beat_index=0):
    return naturalize_detail(text, merge_profile(profile or {}),
                             beat_role=role, beat_index=beat_index, beat_total=5)


def test_hook_last_word_gets_comma_and_bang():
    out = _run("요새 해외 인플루언서들 손에 하나씩 들려있는 이거.", "훅")
    assert ", 이거!" in out, f"③ 규칙(쉼표+느낌표)이 적용 안 됐다: {out!r}"


def test_hook_emphasis_does_not_double_comma():
    """대본이 이미 쉼표를 찍어 왔으면 ',, 이거!'가 되면 안 된다."""
    out = _run("요새 다들 쓰는, 이거.", "훅")
    assert ",," not in out and ", , " not in out, f"쉼표가 겹쳤다: {out!r}"
    assert ", 이거!" in out


def test_hook_emphasis_is_idempotent():
    """이미 규칙이 적용된 문장을 다시 태워도 안 망가진다."""
    once = _run("요새 다들 쓰는 이거.", "훅")
    twice = naturalize_detail(once, merge_profile({}), beat_role="훅",
                              beat_index=0, beat_total=5)["text"]
    assert "!!" not in twice, f"느낌표가 겹쳤다: {twice!r}"
    assert ",," not in twice, f"쉼표가 겹쳤다: {twice!r}"


def test_non_hook_roles_untouched_by_tail_emphasis():
    """반전·실용 문장 끝을 느낌표로 바꾸면 톤이 무너진다(속삭임 반전이 '다르더라고요!').

    ⚠️ 데이터 수정(컨트롤러 지적, 2026-07-17): 원래 문장은 "근데 이건 완전
    다르더라고요."였다. `다르더라고요`는 **6음절**인데 `_HOOK_TAIL_PAT`의
    캡처군은 `[가-힣]{1,5}`(1~5음절)까지만 매치한다 — 즉 이 문장은 role 게이트를
    걷어내도(`emphasis_roles`에 "반전"을 넣어도) 정규식 자체가 매치하지 않아
    애초에 규칙이 발동할 수 없다. 그래서 이 테스트는 게이트가 있어도 없어도 항상
    통과하는 죽은 프로브였다(뮤테이션1을 심어도 안 죽는 것으로 실측 확인).
    "달라요"(3음절)로 바꿔 실제로 패턴이 매치하는 문장으로 교체한다 — 게이트가
    없으면 `'…완전, 달라요!'`가 되어 이 assert가 진짜로 죽는다(뮤테이션1로 검증).
    """
    out = _run("근데 이건 완전 달라요.", "반전")
    assert not out.rstrip().endswith("!"), f"훅 아닌 비트에 느낌표가 붙었다: {out!r}"


def test_hook_single_word_sentence_is_left_alone():
    """어절이 하나뿐이면 앞에 끊을 자리가 없다 — 태그를 걷어낸 본문이 쉼표로 시작하면 안 된다.

    ⚠️ 검증 보강(컨트롤러 지적 Finding3 재검증 중 추가 발견, 2026-07-17): 원래는
    `_run("이거.", "훅")`(기본 프로파일 그대로) + `out.lstrip().startswith(",")`였다.
    두 가지가 겹쳐 뮤테이션3(`_HOOK_TAIL_PAT`의 `(?<=[가-힣])` 제거)을 심어도 죽지
    않는 죽은 프로브였다(실측 확인):
      ① 기본 프로파일은 `fillers.roles=["훅"]`라 beat_index=0에서 항상 발동해
         "이거."가 `_intonation`에 도달하기 전에 이미 "와, 이거."로 바뀐다 —
         "와"가 앞말이 돼 `(?<=[가-힣])` 가드를 (뮤턴트 없이도) 통과시켜버려서
         가드 자체가 시험되지 않는다.
      ② 설령 fillers를 꺼도, `emotion_arc`가 `[curious] ` 태그를 앞에 붙이는데
         `out.lstrip()`은 대괄호를 공백으로 안 쳐서 유령 쉼표가 태그 바로 뒤에
         박혀도(`"[curious], 이거!"`) 문자열은 여전히 "["로 시작해 assert가
         못 잡는다(실측: 뮤턴트 적용 시 `fillers off` 조합에서도 이 assert는
         통과해버림).
      ③ "이거."엔 애초에 공백이 하나도 없어 `\\s+` 자체가 이미 매치를 막는다 —
         가드가 지키는 진짜 자리는 "공백은 있지만 그 앞이 한글이 아닌 자리"
         (태그 바로 뒤)이지 "공백조차 없는 한 단어"가 아니다.
    fillers를 끄고, 태그를 걷어낸 **본문** 기준으로 쉼표 유무를 봐야 가드가 막는
    자리(태그 직후)를 실제로 시험한다(뮤테이션3으로 재검증 완료 — 아래 사용).
    """
    out = _run("이거.", "훅", {"fillers": {"on": False}})
    m = _LEADING_TAGS_PAT.match(out)
    body = out[m.end():] if m else out
    assert not body.lstrip().startswith(","), f"태그 뒤에 유령 쉼표가 붙었다: {out!r}"


def test_existing_adverb_emphasis_still_works():
    """트레일링 부사 강조(부사 앞 쉼표)를 깨뜨리면 안 된다 — 반대편 봉인.

    2026-07-21 재판정 — 옛 문장 "이건 진짜 좋아요. 완전 좋아요. 딱 좋아요."는
    셋 다 intensifier(진짜/완전/딱이 '좋아요'를 직접 수식)라 이제 안 끊는다.
    부사가 트레일링(구두점 앞)으로 오는 문장으로 바꿔 강조가 살아있음을 봉인한다."""
    out = _run("이거 완전. 저건 진짜.", "실용",
               {"intonation": {"intensity": 1.0}})
    assert ", 완전" in out or ", 진짜" in out, \
        f"트레일링 부사 강조가 죽었다: {out!r}"


def test_hook_question_mark_is_preserved_not_flattened():
    """물음표 훅은 건드리지 않는다(리뷰 지적 Critical1, 2026-07-17).

    `_HOOK_TAIL_PAT`의 `([.…!?]*)`가 뒤쪽 문장부호를 통째로 삼키는데 치환은
    하드코딩된 "!"였다 — 그래서 반전의문 훅("이거 뭔지 알아요?")이 하강 느낌표로
    잘못 읽혔다(엔진 원칙: 안 터지는 쪽이 안전한 쪽 — 잘못 터지는 것보다 훨씬 낫다).
    수정 후: 매치된 꼬리의 문장부호에 "?"가 섞여 있으면 규칙이 아예 발동하지 않고
    문장을 그대로 둔다(오늘의 동작 = 질문 훅에겐 리스크 0).
    """
    for text in ["이거 뭔지 알아요?", "왜 다들 이걸 살까요?"]:
        d = _run_detail(text, "훅")
        out = d["text"]
        assert out.rstrip().endswith("?"), f"물음표가 사라졌다: {out!r}"
        assert "!" not in out, f"물음표 훅에 느낌표가 붙었다: {out!r}"
        assert d["applied"].get("intonation", 0) == 0, \
            f"물음표 훅인데 훅꼬리 규칙이 발동해 계상됐다: {d['applied']!r} / {out!r}"


def test_intonation_count_stays_one_when_hook_tail_word_is_adverb():
    """훅 마지막 어절이 그 자체로 부사(`_EMPHASIS_WORDS`)일 때도 카운트는 1이어야
    한다(리뷰 지적 Important, 2026-07-17).

    "완전"은 `_HOOK_TAIL_PAT`(훅 꼬리)과 `_EMPHASIS_PAT`(부사 강조) 둘 다의
    사정권이다 — 순서(꼬리 먼저)가 텍스트가 아니라 **카운트**를 지킨다. 꼬리를
    먼저 태우면 "완전" 자리가 이미 쉼표+느낌표로 바뀌어 `_EMPHASIS_PAT`의
    lookbehind가 더는 그 자리를 후보로 못 잡아 `applied["intonation"]`이 정확히
    1로 남는다. 순서를 뒤집으면(부사 먼저) 같은 글자가 부사 쉼표로 먼저 잡히고
    꼬리 규칙이 다시 한 번 `_bump`해 2로 거짓 계상된다 — `ca92f9c8`이 잡은 유령
    카운트와 같은 결함 클래스다.
    """
    d = _run_detail("가격이 싼데 완전.", "훅")
    assert d["applied"].get("intonation") == 1, \
        f"완전(부사=꼬리 겹침 자리)에서 카운트가 거짓 계상됐다: {d['applied']!r} / {d['text']!r}"
