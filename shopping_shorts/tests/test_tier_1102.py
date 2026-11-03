"""숏클 반 구분(관제 304): 벤치마킹 노하우는 고급 이상, 나머지는 전 반 같다."""
from shopping_shorts import claude_flow as CF, claude_portal as CP


class S:
    def __init__(self, plan):
        self.plan = plan

    def program_members(self):
        return {7: {"plan": self.plan}}


def test_tier_from_member_plan():
    assert CP.member_tier(S("고급반"), 7) == "advanced"
    assert CP.member_tier(S("프리미엄반"), 7) == "premium"
    assert CP.member_tier(S("기본반"), 7) == "basic"
    assert CP.member_tier(S(""), 7) == "basic"
    assert CP.member_tier(S("고급반"), 8) == "basic"


def _call(monkeypatch, plan, body):
    monkeypatch.setattr(CP, "_store", lambda s: S(plan))
    monkeypatch.setattr(CF, "_ensure", lambda s: None)
    monkeypatch.setattr(CP, "_front", lambda *a, **k: (7, None, None))
    return CF.knowhow({}, body)


def test_benchmark_locked_for_basic_open_for_advanced(monkeypatch):
    assert _call(monkeypatch, "기본반", {"topic": "benchmark"})["locked"] is True
    r = _call(monkeypatch, "고급반", {"topic": "benchmark"})
    assert r["guide"] and "locked" not in r


def test_everything_else_same_for_all(monkeypatch):
    a = _call(monkeypatch, "기본반", {"query": "B14 효과음"})
    b = _call(monkeypatch, "프리미엄반", {"query": "B14 효과음"})
    assert a["matched"] == b["matched"] and a["guide"] == b["guide"]
