"""다시 시도 갈 곳 = flow._retry_route 한 곳(Jev 11-07 F5 — 뿌리 0.88·근본 0.85·한줄기 0.77·두더지 0.08).
고치기 한도·같은 원인 연속(_tries) 멈춤은 다시 시도로 안 풀린다(사장님 11-02 '다시 시도는 횟수를 지우지 않는다').
옛 답을 다시 먹여 회원이 고친 대본 파일을 덮던 길을 막는다(이성택 557 sid 70a2c65a732b #12641~#12661 · 이만수 720 #12096).
같은 꼴 이전 수리: 2d03e9904(원본 못 찾음) · 533c1b666(완성본 고치기) — 단계마다 땜하던 것을 한 곳으로."""
import pytest

from tools.calcopy.hybrid import flow as F

OLD = {"script_썰템쇼판": {"대본": {"lines": []}, "재료": {}}}


def _st(**kw):
    return {"version": "썰템쇼판", "log": [], "tries": {"script": F.LIMITS["script"]}, "redo_hist": {"script": [["orig_heard"]] * 3},
            "read": {}, "product": {}, "_asker": "script_got", "_asker_in": {"rp": OLD}, **kw}


def test_redo_stop_carries_key():
    st = _st()
    with pytest.raises(F._Stop) as ei:
        F._tries(st, "script", F.LIMITS["script"], ["orig_heard"])
    assert ei.value.redo == "script"


def test_route_owner_refuses_redo_and_keeps_replay_for_transient():
    st = _st()
    assert F._retry_route(st, "script_got", "script") is None
    assert F._retry_route(st, "script_got", None) == {"goto": "script_got", "feed": {"rp": OLD}}
    assert F._retry_route(st, "plan", None) == {"goto": "plan"}


def _redo_task(st):
    det = "고치기 한도 script 6번 · 원인 ['orig_heard']"
    e = F._Stop("원래 목소리 자리가 끝내 안 맞았어요", "x", retry="script_got", redo="script", detail=det)
    task = F._task(st, e, "script_heard", "script_got")
    assert task and st["_task"]["redo"] == "script"
    st["phase"] = "task_got"
    return task


def test_task_retry_on_redo_stop_reasks_task_without_replay():
    st = _st()
    _redo_task(st)
    res = F.step(st, {}, {"task_1": {"action": "retry", "note": "다시"}}, {})
    assert res.get("status") == "review" and st["phase"] == "task_got"           # 과제를 다시 묻는다
    assert not any(d.get("cmd") == "write_doc" for d in res.get("do") or [])     # 옛 대본 답으로 대본.json 을 다시 쓰지 않는다
    ask = str(res["review"][0])
    assert "retry" in ask and "back" in ask and "안 듣" in ask                       # 첫 줄 안내
    assert st["tries"]["script"] == F.LIMITS["script"]                            # 사장님 11-02 — 횟수 그대로
    assert st["task_n"][st["_task"]["key"]] == 2                                   # 같은 막힘 열쇠로 센다(뺑뺑이 상한 TASK_PER_KEY)
    assert st["_task"]["stage"] == "script" and st["_task"]["redo"] == "script"    # 다시 낸 과제도 멈춘 단계 그대로
    out = F.ph_task_got(st, {}, {st["_task"]["id"]: {"action": "back", "to": "script"}}, {})
    assert out == {"goto": "script"} and "script" not in st["tries"]               # back 은 그 단계 횟수를 비우고 새로


def test_task_retry_on_redo_stops_after_per_key_limit():
    st = _st()
    _redo_task(st)
    for _ in range(F.TASK_PER_KEY):
        res = F.step(st, {}, {st["_task"]["id"]: {"action": "retry"}}, {})
    assert res.get("status") == "stop"                                             # 끝없이 과제를 내지 않는다


def test_member_button_retry_on_redo_stop_gives_task_not_replay(monkeypatch):
    monkeypatch.setattr(F, "audit_script", lambda st, S, M: {"ok": True})       # 옛 길이면 옛 답이 그대로 통과해 대본.json 을 다시 쓴다
    monkeypatch.setattr(F, "_prep_material", lambda st, S, M: M)
    st = _st(phase="stopped", stopped={"why": "원래 목소리 자리가 끝내 안 맞았어요", "fix": "x", "retry": "script_got", "redo": "script",
                                         "detail": "고치기 한도 script 6번 · 원인 ['orig_heard']"})
    res = F.step(st, {}, {}, {"retry": True})
    assert not any(d.get("cmd") == "write_doc" for d in res.get("do") or [])
    assert res.get("status") in ("review", "stop")


def test_transient_task_retry_still_replays():
    st = _st(tries={})
    st.update({"phase": "task_got", "_task": {"id": "task_1", "stage": "script", "retry": "script_got", "why": "w", "fix": "f"}})
    out = F.ph_task_got(st, {}, {"task_1": {"action": "retry"}}, {})
    assert out == {"goto": "script_got", "feed": {"rp": OLD}}
