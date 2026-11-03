import pytest
from tools.calcopy.hybrid import jev_gate as J

class Ans:
    def __init__(self, **kw): self.__dict__.update(kw)

class FakeClient:
    def __init__(self, answers): self.answers = answers
    def system_one(self, state, questions, **kw):
        assert "fix_0" in state and "best_fix" in questions
        return Ans(answers=self.answers)

def test_decide_picks_and_marks_ok():
    a = {"fixroot_0": Ans(type="noul", noul=0.8), "fixroot_1": Ans(type="noul", noul=0.2),
         "best_fix": Ans(type="choice", choice="fix_0", confidence=0.91)}
    r = J.decide("p", ["f"], ["A", "B"], client=FakeClient(a))
    assert r == {"pick": 0, "conf": 0.91, "fixroot": [0.8, 0.2], "ok": True}

def test_low_confidence_not_ok():
    a = {"fixroot_0": Ans(type="noul", noul=0.5), "fixroot_1": Ans(type="noul", noul=0.5),
         "best_fix": Ans(type="choice", choice="fix_1", confidence=0.52)}
    assert J.decide("p", [], ["A", "B"], client=FakeClient(a))["ok"] is False

def test_needs_two_fixes():
    with pytest.raises(ValueError):
        J.decide("p", [], ["A"], client=FakeClient({}))

def test_no_key_raises_jevdown(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(J.JevDown):
        J.decide("p", [], ["A", "B"])
