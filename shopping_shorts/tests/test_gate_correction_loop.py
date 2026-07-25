"""게이트 교정 루프(2026-07-25) — 위반이면 통과할 때까지 재픽(상한 3), 수렴하면 종료.
plan_gate는 최종 계획을 보는 유일한 지점이라 여기서 교정해야 쳇바퀴가 끊긴다."""
from shopping_shorts import mix_pipeline, backbone


def test_loop_repicks_until_gate_ok(monkeypatch):
    calls = {"repick": 0}

    def fake_check(beats, target=None, pool_video_count=None):
        ok = calls["repick"] >= 1  # 한 번 재픽하면 통과
        return {"ok": ok,
                "violations": [] if ok else ["컷 없이 이어지는 구간 1곳 — 원본을 그대로 트는 느낌"]}

    def fake_repick(beats, pool, gate):
        calls["repick"] += 1
        return [{"primary": {"seg_id": "s1-0", "video_id": "s1"}}]

    monkeypatch.setattr(mix_pipeline.plan_gate, "check_plan", fake_check)
    monkeypatch.setattr(backbone, "repick_for_gate", fake_repick)
    plan = {"beats": [{"primary": {"seg_id": "s0-4", "video_id": "s0"}}]}
    mix_pipeline._run_gate_correction(plan, [{"video_id": "s0", "segments": [1]}], 30)
    assert calls["repick"] == 1
    assert plan["gate"]["ok"] is True
    assert plan["beats"][0]["primary"]["seg_id"] == "s1-0"
    assert plan["repick_rounds"] == 1


def test_loop_terminates_when_repick_no_change(monkeypatch):
    def fake_check(beats, target=None, pool_video_count=None):
        return {"ok": False,
                "violations": ["컷 없이 이어지는 구간 1곳 — 원본을 그대로 트는 느낌"]}

    monkeypatch.setattr(mix_pipeline.plan_gate, "check_plan", fake_check)
    monkeypatch.setattr(backbone, "repick_for_gate", lambda beats, pool, gate: beats)  # 변화 없음
    plan = {"beats": [{"primary": {"seg_id": "s0-4", "video_id": "s0"}}]}
    mix_pipeline._run_gate_correction(plan, [{"video_id": "s0", "segments": [1]}], 30)
    assert plan["gate"]["ok"] is False       # 잔여 위반 남김(정상 종료)
    assert plan["repick_rounds"] == 0        # 첫 재픽이 무변화 → 즉시 종료


def test_length_violation_not_repicked(monkeypatch):
    """길이 짧음은 재픽 불가(생성 영역) → repick 호출 안 하고 gate만 저장."""
    calls = {"repick": 0}

    def fake_check(beats, target=None, pool_video_count=None):
        return {"ok": False, "violations": ["길이가 21.3초로 목표 30초보다 많이 짧습니다"]}

    def fake_repick(beats, pool, gate):
        calls["repick"] += 1
        return beats

    monkeypatch.setattr(mix_pipeline.plan_gate, "check_plan", fake_check)
    monkeypatch.setattr(backbone, "repick_for_gate", fake_repick)
    plan = {"beats": [{"primary": {"seg_id": "s0-4", "video_id": "s0"}}]}
    mix_pipeline._run_gate_correction(plan, [{"video_id": "s0", "segments": [1]}], 30)
    assert calls["repick"] == 0              # 길이 위반엔 재픽 안 함
    assert plan["gate"]["ok"] is False
