"""script_chat.revise 계약(관제 253) — 대화만 하면 대본 그대로 · edit 때만 같은 줄 수로 고침 · 한 줄 요구(only)는 그 줄만 ·
빈 줄 거부 · 빈 칸 표시 되돌림."""
import pytest

from shopping_shorts import script_chat


def _edit(lines, reply="고쳤어요"):
    return lambda p, s: {"reply": reply, "edit": True, "lines": lines}


def test_chat_only_keeps_script():
    out = script_chat.revise(["첫 줄", "둘째 줄"], "훅 후보 3개 추천해줘",
                             call=lambda p, s: {"reply": "1. 가\n2. 나\n3. 다", "edit": False})
    assert out["reply"].startswith("1. 가") and out["lines"] == ["첫 줄", "둘째 줄"] and out["changed"] == []


def test_chat_only_ignores_stray_lines():
    out = script_chat.revise(["a", "b"], "어때?", call=lambda p, s: {"reply": "좋아요", "edit": False, "lines": ["x", "y"]})
    assert out["lines"] == ["a", "b"] and out["changed"] == []


def test_edit_returns_changed_rows_only():
    out = script_chat.revise(["첫 줄", "둘째 줄", "셋째 줄"], "2번째 줄 짧게", call=_edit(["첫 줄", "짧게", "셋째 줄"]))
    assert out["lines"] == ["첫 줄", "짧게", "셋째 줄"] and out["changed"] == [1] and out["auth"] == "free"


def test_prompt_carries_lines_roles_and_history():
    seen = {}

    def call(p, s):
        seen["p"] = p
        return {"reply": "ok", "edit": False}
    script_chat.revise(["a", "b"], "2번째 걸로 해줘", roles=["훅", "문제"],
                       history=[{"role": "user", "text": "훅 후보"}, {"role": "ai", "text": "1. 가\n2. 나"}], call=call)
    p = seen["p"]
    assert "1. [훅] a" in p and "2. [문제] b" in p and "회원: 훅 후보" in p and "AI: 1. 가" in p and "정확히 2줄" in p


def test_only_row_changes_even_if_ai_touches_others():
    seen = {}

    def call(p, s):
        seen["p"] = p
        return {"reply": "x", "edit": True, "lines": ["A", "B", "C"]}
    out = script_chat.revise(["a", "b", "c"], "연결어로 바꿔줘", roles=["훅", "문제", "해결"], only=1, call=call)
    assert out["lines"] == ["a", "B", "c"] and out["changed"] == [1]
    assert "2번 줄(문제)만" in seen["p"]


def test_only_row_requires_a_change():
    with pytest.raises(ValueError, match="고치지 않"):
        script_chat.revise(["a", "b"], "다른 스타일로", only=0, call=lambda p, s: {"reply": "음", "edit": False}, tries=1)
    with pytest.raises(ValueError, match="같은 문장"):
        script_chat.revise(["a", "b"], "다른 스타일로", only=0, call=_edit(["a", "X"]), tries=1)
    with pytest.raises(ValueError, match="줄 번호"):
        script_chat.revise(["a", "b"], "x", only=5, call=_edit(["a", "b"]))


def test_line_count_mismatch_retries_then_fails():
    calls = []

    def call(p, s):
        calls.append(1)
        return {"reply": "x", "edit": True, "lines": ["하나"]}
    with pytest.raises(ValueError, match="줄 수"):
        script_chat.revise(["a", "b"], "고쳐", call=call)
    assert len(calls) == 2


def test_empty_ai_says_empty():
    with pytest.raises(ValueError, match="응답이 비었"):
        script_chat.revise(["a", "b"], "고쳐", call=lambda p, s: {})


def test_blank_line_for_filled_row_rejected():
    with pytest.raises(ValueError, match="빈 줄"):
        script_chat.revise(["a", "b"], "고쳐", call=_edit(["a", ""]), tries=1)


def test_empty_slot_may_stay_empty_and_empty_board_can_be_filled():
    assert script_chat.revise(["a", ""], "고쳐", call=_edit(["A", ""]))["changed"] == [0]
    out = script_chat.revise(["", ""], "대본 써줘", call=_edit(["가", "나"]))
    assert out["lines"] == ["가", "나"] and out["changed"] == [0, 1]


def test_empty_mark_echo_is_blanked():
    out = script_chat.revise(["a", "", ""], "훅 바꿔", call=_edit(["A", "(빈 칸)", "빈칸"]))
    assert out["lines"] == ["A", "", ""] and out["changed"] == [0]


@pytest.mark.parametrize("lines,msg,err", [([], "x", "칸이 없"), (["a"], " ", "말을")])
def test_bad_input(lines, msg, err):
    with pytest.raises(ValueError, match=err):
        script_chat.revise(lines, msg, call=lambda p, s: {"reply": "x", "edit": False})
