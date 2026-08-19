"""훅 감탄사 로테이션(2026-08-11 사장님 '1번으로 수정') — add_hook_opener.

규칙: 질문형=무부착 / 명령·권유형='여러분 ' / 서술형=해시 절반 '와, '·절반 무부착.
"""
from shopping_shorts import single_source as ss


def _beats(first):
    return [{"narration": first}, {"narration": "두번째 문장이에요."}]


def test_question_gets_no_opener():
    b = ss.add_hook_opener(_beats("이거 왜 이렇게 반짝거리는지 아세요?"))
    assert b[0]["narration"].startswith("이거")


def test_imperative_gets_yeorobun():
    b = ss.add_hook_opener(_beats("다이소 가면 이건 꼭 사오세요."))
    assert b[0]["narration"].startswith("여러분 다이소")


def test_declarative_split_half_and_half():
    outs = set()
    for i in range(30):
        first = f"구축 화장실이 호텔처럼 변했더라고요 {i}."
        n = ss.add_hook_opener(_beats(first))[0]["narration"]
        outs.add(n.startswith("와, "))
    assert outs == {True, False}             # 두 갈래 모두 나온다(로테이션)


def test_deterministic_per_script():
    first = "구축 화장실이 호텔처럼 변했더라고요."
    a = ss.add_hook_opener(_beats(first))[0]["narration"]
    b = ss.add_hook_opener(_beats(first))[0]["narration"]
    assert a == b                            # 같은 대본 → 같은 결과(재생성 흔들림 없음)


def test_never_double_wa():
    # 관문(hook_opener_missing)이 막지만, 직접 불러도 '와, 와'는 없어야 안전하다.
    for i in range(30):
        first = f"화장실이 호텔처럼 변했더라고요 {i}."
        n = ss.add_hook_opener(_beats(first))[0]["narration"]
        assert "와, 와" not in n and "여러분 여러분" not in n
