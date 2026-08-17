# -*- coding: utf-8 -*-
"""대본 지문 `_script_hash` — 3단계 자동 재매칭의 판정 기준 (2026-08-17).

★왜 테스트가 필요한가:
  3단계는 들어올 때마다 "지금 job이 **지금 대본**으로 만들어진 것인가"를 이 해시로
  판정하고, 다르면 **자동으로 다시 매칭한다**(사장님 결정 A). 그런데 매칭은 과금이다
  (render 1회 차감). 서버(app.py `_script_hash`)와 프론트(produce.html `_scriptHash`)의
  규칙이 조금이라도 어긋나면 **항상 '바뀐 것'으로 보여 무한 재매칭 = 요금**이 된다.
  짝으로 움직이는 값이므로 규칙을 못 박아 둔다(CLAUDE.md 0순위-B).

  JS와의 일치는 실측으로 확인했다(2026-08-17, 6케이스 전부 동일):
    ["53338f187158a5be","1faf405e44602429","f288d4beb8b0aa0d","fcd127ffa1016069","","60b1939e0ce0297f"]
  ⚠️ 이 값을 바꾸려면 produce.html의 `_scriptHash`도 **같이** 고쳐야 한다.

핵심 성질: 사람이 보기에 같은 글이면 같은 해시여야 한다.
줄 끝 공백·CRLF는 편집기·저장 경로에 따라 저절로 생겼다 사라진다 — 그걸로 "대본이
바뀌었다"고 판정하면 아무도 안 고쳤는데 매칭이 다시 돌아 돈이 나간다.
"""
from shopping_shorts.app import _script_hash


# 프론트(_scriptHash)와 대조해 실측한 고정값 — 여기가 바뀌면 JS도 바뀌어야 한다.
_KNOWN = {
    "아침마다 밀가루 빵 먹는다고\n엄마한테 욕 먹을 뻔했어요": "53338f187158a5be",
    "  앞뒤공백  ": "1faf405e44602429",
    "줄끝공백   \n다음줄": "f288d4beb8b0aa0d",
    "a\r\nb": "fcd127ffa1016069",
    "": "",
    "한글 テスト 🍞": "60b1939e0ce0297f",
}


def test_matches_frontend_known_values():
    """JS `_scriptHash`와 실측 대조한 값 — 어긋나면 무한 재매칭(과금)이 난다."""
    for text, expected in _KNOWN.items():
        assert _script_hash(text) == expected, "JS와 어긋남: %r" % text


def test_trailing_whitespace_does_not_change_hash():
    """줄 끝 공백은 무시 — 저절로 생기는 차이로 재매칭이 돌면 안 된다."""
    assert _script_hash("첫 줄\n둘째 줄") == _script_hash("첫 줄   \n둘째 줄\t")


def test_crlf_and_lf_are_same():
    """CRLF/LF 차이도 무시 — 같은 글이다."""
    assert _script_hash("a\r\nb\r\nc") == _script_hash("a\nb\nc")


def test_outer_whitespace_ignored():
    """앞뒤 공백·빈 줄도 같은 글로 본다."""
    assert _script_hash("  본문  \n\n") == _script_hash("본문")


def test_empty_is_empty_string():
    """빈 대본은 빈 지문 — 프론트가 이걸 보고 '판정 불가'로 넘긴다."""
    for empty in ("", "   ", "\n\n", None):
        assert _script_hash(empty) == ""


def test_real_change_changes_hash():
    """진짜로 고치면 반드시 달라져야 한다(안 그러면 옛 영상이 그대로 나간다)."""
    a = _script_hash("아침마다 요거트 식빵을 먹어요")
    b = _script_hash("아침마다 요거트 케이크를 먹어요")
    assert a and b and a != b


def test_hash_is_short_and_stable():
    """길이 16 — 응답에 실어도 가볍고, 충돌 걱정할 자릿수는 된다."""
    h = _script_hash("아무 대본")
    assert len(h) == 16 and h == _script_hash("아무 대본")
