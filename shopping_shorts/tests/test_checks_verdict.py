from shopping_shorts.checks.verdict import summarize, RED, GREEN, GRAY, YELLOW


def _row(sig, v, name=None):
    return {"signature": sig, "verdict": v, "name": name or sig, "layer": "L1"}


def test_newly_red_is_red_now_and_not_red_before():
    rows = [_row("a", RED), _row("b", RED), _row("c", GREEN)]
    out = summarize(rows, prev={"a": GREEN, "b": RED})
    assert [r["signature"] for r in out["newly_red"]] == ["a"]
    assert out["counts"] == {"red": 2, "yellow": 0, "gray": 0, "green": 1}
    assert out["overall"] == RED


def test_red_wins_over_gray_and_first_time_red_counts_as_new():
    # ★2026-09-07 리뷰 지적으로 우선순위가 바뀌었다: 회색이 상시로 깔려도(RED>GRAY>YELLOW>GREEN)
    # 종합 신호등이 영구 회색이 되지 않도록 RED가 최우선이다.
    out = summarize([_row("x", GRAY), _row("y", RED)], prev={})
    assert out["overall"] == RED
    assert [r["signature"] for r in out["newly_red"]] == ["y"]


def test_headline_korean():
    out = summarize([_row("대본 왕복", RED)], prev={"대본 왕복": GREEN})
    assert "대본 왕복" in out["headline"] and "새로" in out["headline"]
    assert summarize([_row("a", GREEN)], prev={})["headline"] == "전부 정상입니다."
