"""script_chat.revise 계약(관제 253) — 줄 수 그대로·빈 줄 거부·바뀐 줄 번호·빈 응답 안내."""
import pytest

from shopping_shorts import script_chat


def test_revise_returns_changed_rows_only():
    src = ["첫 줄", "둘째 줄", "셋째 줄"]
    out = script_chat.revise(src, "2번째 줄 짧게", call=lambda p, s: {"reply": "고쳤어요", "lines": ["첫 줄", "짧게", "셋째 줄"]})
    assert out["lines"] == ["첫 줄", "짧게", "셋째 줄"]
    assert out["changed"] == [1]
    assert out["auth"] == "free"


def test_prompt_carries_lines_and_history():
    seen = {}

    def call(p, s):
        seen["p"] = p
        return {"reply": "ok", "lines": ["a", "b"]}
    script_chat.revise(["a", "b"], "반말로", history=[{"role": "user", "text": "훅 세게"}, {"role": "ai", "text": "했어요"}], call=call)
    assert "1. a" in seen["p"] and "2. b" in seen["p"] and "회원: 훅 세게" in seen["p"] and "정확히 2줄" in seen["p"]


def test_line_count_mismatch_retries_then_fails():
    calls = []

    def call(p, s):
        calls.append(1)
        return {"reply": "x", "lines": ["하나"]}
    with pytest.raises(ValueError, match="줄 수"):
        script_chat.revise(["a", "b"], "고쳐", call=call)
    assert len(calls) == 2


def test_empty_ai_says_empty_not_line_count():
    with pytest.raises(ValueError, match="응답이 비었"):
        script_chat.revise(["a", "b"], "고쳐", call=lambda p, s: {})


def test_blank_line_for_filled_row_rejected():
    with pytest.raises(ValueError, match="빈 줄"):
        script_chat.revise(["a", "b"], "고쳐", call=lambda p, s: {"reply": "x", "lines": ["a", ""]}, tries=1)


def test_empty_slot_may_stay_empty():
    out = script_chat.revise(["a", ""], "고쳐", call=lambda p, s: {"reply": "x", "lines": ["A", ""]})
    assert out["lines"] == ["A", ""] and out["changed"] == [0]


@pytest.mark.parametrize("lines,msg,err", [([], "x", "대본이 없"), (["", ""], "x", "대본이 없"), (["a"], " ", "요청")])
def test_bad_input(lines, msg, err):
    with pytest.raises(ValueError, match=err):
        script_chat.revise(lines, msg, call=lambda p, s: {"reply": "", "lines": lines})
