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

def _ans(choice, conf=0.9):
    return {"fixroot_0": Ans(type="noul", noul=0.5), "fixroot_1": Ans(type="noul", noul=0.5),
            "best_fix": Ans(type="choice", choice=choice, confidence=conf)}

def test_none_choice():
    r = J.decide("p", [], ["A", "B"], client=FakeClient(_ans("none")))
    assert r["pick"] is None and r["ok"] is False

def test_client_exception_is_jevdown():
    class Boom:
        def system_one(self, **kw): raise RuntimeError("x")
    with pytest.raises(J.JevDown):
        J.decide("p", [], ["A", "B"], client=Boom())

def test_missing_best_fix_bad_answer():
    with pytest.raises(J.JevDown, match="bad_answer"):
        J.decide("p", [], ["A", "B"], client=FakeClient({"fixroot_0": Ans(noul=0.5), "fixroot_1": Ans(noul=0.5)}))

def test_out_of_range_pick():
    r = J.decide("p", [], ["A", "B"], client=FakeClient(_ans("fix_5")))
    assert r["pick"] is None and r["ok"] is False
