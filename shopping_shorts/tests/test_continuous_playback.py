"""연속재생(컷 없음) 회귀 — 2026-07-24 실사고: seg_id는 전부 고유인데 원본 인접구간을
시간순으로 붙여 '원본을 그냥 트는' 화면이 나왔다(사장님: 10·14·16·22초 연속재생).
고유성 게이트는 통과했으므로 '이어붙임'을 따로 잡아야 한다.
"""
from shopping_shorts import backbone, plan_gate


def _clip(seg, vid, start, end):
    return {"seg_id": seg, "video_id": vid, "start": start, "end": end}


def _beat(primary, alts=(), secs=3.0):
    return {"primary": primary, "alternates": list(alts), "target_seconds": secs}


# ── is_continuous ─────────────────────────────────────────────
def test_adjacent_same_source_is_continuous():
    a = _clip("s2-0", "s2", 0.0, 1.8)
    b = _clip("s2-1", "s2", 1.8, 3.1)          # 앞 끝 == 뒤 시작
    assert backbone.is_continuous(a, b) is True


def test_different_source_is_a_cut():
    a = _clip("s2-0", "s2", 0.0, 1.8)
    b = _clip("s0-4", "s0", 1.8, 3.1)
    assert backbone.is_continuous(a, b) is False


def test_far_apart_same_source_is_a_cut():
    a = _clip("s2-0", "s2", 0.0, 1.8)
    b = _clip("s2-9", "s2", 12.7, 13.3)
    assert backbone.is_continuous(a, b) is False


# ── 게이트가 실사고 패턴을 잡는가 ────────────────────────────
def test_gate_catches_the_real_incident_pattern():
    """실제 job 740670fdf57b 모양: s2-0~s2-5를 순서대로 이어붙임 = 고유하지만 컷 없음."""
    beats = [
        _beat(_clip("s2-0", "s2", 0.0, 1.8), [_clip("s2-1", "s2", 1.8, 3.1)]),
        _beat(_clip("s2-2", "s2", 3.1, 5.6), [_clip("s2-3", "s2", 5.6, 6.6)]),
        _beat(_clip("s2-4", "s2", 6.6, 7.7), [_clip("s2-5", "s2", 7.7, 9.0)]),
    ]
    r = plan_gate.check_plan(beats, target_seconds=9)
    assert r["repeat_segs"] == []                       # 반복은 0 — 옛 게이트는 통과했었다
    assert not r["ok"]
    assert any("컷 없이" in v for v in r["violations"])   # 이제 잡힌다
    assert r["continuous_runs"] and r["continuous_runs"][0]["clips"] >= 3


def test_gate_ok_when_really_cut():
    beats = [
        _beat(_clip("s2-0", "s2", 0.0, 1.8), [_clip("s0-7", "s0", 20.0, 21.5)]),
        _beat(_clip("s1-3", "s1", 4.0, 5.8), [_clip("s2-9", "s2", 12.7, 14.0)]),
        _beat(_clip("s0-1", "s0", 1.0, 2.9), [_clip("s1-8", "s1", 30.0, 31.4)]),
        _beat(_clip("s2-14", "s2", 40.0, 41.6), [_clip("s0-3", "s0", 8.0, 9.4)]),
        _beat(_clip("s1-1", "s1", 2.0, 3.7), [_clip("s2-20", "s2", 55.0, 56.5)]),
    ]
    r = plan_gate.check_plan(beats, target_seconds=15)
    assert r["ok"], r["violations"]


# ── dedup가 이어붙임 alternate를 갈아끼우는가 ────────────────
def test_dedup_replaces_continuous_alternate():
    beats = [_beat(_clip("s2-0", "s2", 0.0, 1.8), [_clip("s2-1", "s2", 1.8, 3.1)])]
    pool = [{"video_id": "s2", "segments": [
        {"seg_id": "s2-0", "start": 0.0, "end": 1.8, "scene_desc": "a"},
        {"seg_id": "s2-1", "start": 1.8, "end": 3.1, "scene_desc": "b"},
        {"seg_id": "s2-9", "start": 12.7, "end": 14.2, "scene_desc": "완성된 요리 클로즈업"},
    ]}]
    out = backbone.dedup_clips_global(beats, pool)
    alts = out[0].get("alternates") or []
    # s2-1(이어붙임)은 그대로 쓰이면 안 된다 — 교체되거나 드롭
    assert all(a.get("seg_id") != "s2-1" for a in alts)
