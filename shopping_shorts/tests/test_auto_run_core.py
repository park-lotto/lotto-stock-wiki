"""러너 코어 — DI 루프의 판정·원가·재개·알림(스펙 §4·§5, 트랙4).

실 엔진 없이 가짜 단계 함수로 오케스트레이션만 검증한다.
"""
import pytest
from shopping_shorts.store import Store
from shopping_shorts import auto_run
from shopping_shorts.auto_run import StageResult, Verdict, run_auto_job


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def _stage(ref, cost=0.0):
    def fn(ctx):
        return StageResult(output_ref=ref, metrics={"cost_krw": cost})
    return fn


def _stages(**over):
    base = {"S1": _stage("reel1"), "S2": _stage("script1"), "S3": _stage("video1")}
    base.update(over)
    return base


def test_all_pass_reaches_done(store):
    store.create_auto_job("J1")
    out = run_auto_job("J1", store, stages=_stages())
    assert out["status"] == "done"
    assert out["current_stage"] == "S3"
    r = store.get_auto_job("J1")["stage_results"]
    assert r["S1"]["output_ref"] == "reel1" and r["S3"]["output_ref"] == "video1"


def test_unsure_stops_and_notifies(store):
    store.create_auto_job("J1")
    sent = []

    def judge(name, result, ctx):
        return Verdict("unsure", ["애매"]) if name == "S2" else Verdict("pass")
    out = run_auto_job("J1", store, stages=_stages(), judge=judge,
                       notifier=lambda text: sent.append(text))
    assert out["status"] == "waiting_human"
    assert out["current_stage"] == "S2"           # 멈춘 자리
    assert len(sent) == 1 and "S2" in sent[0]
    # S3는 실행되지 않았다
    assert "S3" not in store.get_auto_job("J1")["stage_results"]


def test_fail_retries_then_escalates_to_unsure(store):
    store.create_auto_job("J1")
    calls = {"n": 0}

    def s2(ctx):
        calls["n"] += 1
        return StageResult(output_ref=f"try{calls['n']}")

    def judge(name, result, ctx):
        return Verdict("fail", ["별로"]) if name == "S2" else Verdict("pass")
    out = run_auto_job("J1", store, stages=_stages(S2=s2), judge=judge, max_retries=2)
    assert calls["n"] == 3                          # 최초 + 재시도2
    assert out["status"] == "waiting_human"          # 소진 후 unsure 승격
    assert out["current_stage"] == "S2"


def test_cost_cap_forces_unsure_no_retry(store):
    store.create_auto_job("J1")
    out = run_auto_job("J1", store, stages=_stages(S1=_stage("r", cost=1500.0)),
                       cost_cap_krw=1000)
    assert out["status"] == "waiting_human"
    assert out["unsure_reason"] == "cost_cap"
    assert out["current_stage"] == "S1"
    assert out["cost_krw"] == 1500.0


def test_cost_accumulates_across_stages(store):
    store.create_auto_job("J1")
    out = run_auto_job("J1", store, stages=_stages(
        S1=_stage("a", 300), S2=_stage("b", 300), S3=_stage("c", 300)))
    assert out["status"] == "done"
    assert out["cost_krw"] == 900.0


def test_resume_skips_completed_stages(store):
    store.create_auto_job("J1")
    # S1 이미 통과한 상태로 만든다(재개 시뮬)
    store.update_auto_job("J1", current_stage="S1",
                          stage_results={"S1": {"output_ref": "reel1", "metrics": {}}})
    ran = []

    def track(name, ref):
        def fn(ctx):
            ran.append(name)
            return StageResult(output_ref=ref)
        return fn
    run_auto_job("J1", store, stages={"S1": track("S1", "x"),
                                      "S2": track("S2", "s"), "S3": track("S3", "v")})
    assert ran == ["S2", "S3"]                       # S1 재실행 안 함


def test_default_judge_is_pass():
    assert auto_run.default_judge("S1", StageResult(), {}).decision == "pass"


def test_notifier_none_does_not_crash(store):
    store.create_auto_job("J1")

    def judge(name, result, ctx):
        return Verdict("unsure") if name == "S1" else Verdict("pass")
    out = run_auto_job("J1", store, stages=_stages(), judge=judge, notifier=None)
    assert out["status"] == "waiting_human"          # 알림기 없어도 정상 멈춤
