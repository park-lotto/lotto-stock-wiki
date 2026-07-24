"""P2 렌더 직전 불변식 게이트 — 뒷단계가 앞단계를 되돌려도 최종 plan에서 잡히는지."""
from shopping_shorts import plan_gate


def _beat(primary, alts=(), secs=3.0):
    return {"primary": {"seg_id": primary}, "target_seconds": secs,
            "alternates": [{"seg_id": s} for s in alts]}


def test_clean_plan_passes():
    beats = [_beat("s%d" % i, ["a%d" % i]) for i in range(6)]
    r = plan_gate.check_plan(beats, target_seconds=18)
    assert r["ok"] and r["violations"] == []


def test_cross_beat_repeat_is_caught():
    """비트 사이 같은 장면 반복 = 사장님이 제일 싫어하는 것 → 반드시 잡힌다."""
    beats = [_beat("s0", ["b1"]), _beat("s1", ["b1"]), _beat("s2", ["b1"])]
    r = plan_gate.check_plan(beats, target_seconds=9)
    assert not r["ok"]
    assert any("반복" in v for v in r["violations"])
    assert "b1" in r["repeat_segs"]


def test_too_few_beats_caught():
    r = plan_gate.check_plan([_beat("s0"), _beat("s1")], target_seconds=6)
    assert not r["ok"] and any("비트" in v for v in r["violations"])


def test_short_length_caught():
    """30초 목표인데 20초면 빈약(옛 생성기 폴백의 전형적 증상)."""
    beats = [_beat("s%d" % i, secs=3.3) for i in range(6)]   # 약 19.8초
    r = plan_gate.check_plan(beats, target_seconds=30)
    assert not r["ok"] and any("짧" in v for v in r["violations"])


def test_fragmented_beat_caught():
    beats = [_beat("s%d" % i, ["x%d" % i, "y%d" % i, "z%d" % i, "w%d" % i]) for i in range(6)]
    r = plan_gate.check_plan(beats, target_seconds=18)
    assert not r["ok"] and any("쪼개" in v for v in r["violations"])


def test_empty_is_safe():
    r = plan_gate.check_plan([], target_seconds=30)
    assert r["beat_count"] == 0 and isinstance(r["violations"], list)
    r2 = plan_gate.check_plan(None)
    assert r2["beat_count"] == 0
