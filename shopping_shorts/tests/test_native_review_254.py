"""원어민 역할 검수(관제 254) — 2명 이상이 어색하다 해야 문제 줄, 죽은 심사위원은 이유와 함께 빠진다, 다른 언어 고친 문장은 버린다."""
from shopping_shorts import native_review as nr


def _j(scores, fix=""):
    return lambda prompt: {"lines": [{"i": i, "score": s, "problem": "x" if s <= 3 else "", "fix": fix if s <= 3 else ""}
                                     for i, s in enumerate(scores)]}


def test_two_votes_needed_and_dead_judge_skipped(monkeypatch):
    def dead(prompt):
        raise RuntimeError("quota")
    monkeypatch.setattr(nr, "JUDGES", {"a": _j([5, 2, 2], "这个太好用了"), "b": _j([2, 2, 5], "这个太好用了"),
                                       "c": _j([5, 1, 5], "これ最高"), "d": dead})
    r = nr.review(["一", "二", "三"], "zh")
    assert [x["flagged"] for x in r["lines"]] == [False, True, False]
    assert r["lines"][1]["fix"] == "这个太好用了"          # 일본어로 쓴 고친 문장(c)은 버려진다
    assert "d" in r["skipped"] and r["judges"] == ["a", "b", "c"]
