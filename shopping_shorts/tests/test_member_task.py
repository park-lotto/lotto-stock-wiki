# -*- coding: utf-8 -*-
"""관제263 10-26 사장님 "우리가 직접 만드는 것같이 — 가이드를 지키며, 문제가 생기면 헤쳐 나간다" — flow 멈춤은 회원에게 '다시 시도'를 묻기 전에
회원 Claude(제작자)에게 과제(목표·가이드 발췌·함정·답 꼴)로 간다. 판단 주인 = flow._task(멈춤 → 과제) · flow.ph_task_got(답 → 기존 이어 가기 ph_stopped).
결과 검사는 각 단계 원래 판정 그대로. 회원에게 바로 가는 것 = final(금지선) · ask_member(키·준비·한도 뒤) · 과제 한도."""
from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.calcopy.hybrid import flow as F  # noqa: E402
import test_flow_formats as TF  # noqa: E402


def _measure(d, ctx):
    if d["cmd"] == "bench":
        ctx["bench_calls"] = ctx.get("bench_calls", 0) + 1
        if ctx["bench_calls"] <= ctx.get("bench_fail", 0):
            return {"error": "벤치 영상을 받지 못했다 — ERROR: Video unavailable"}
    return TF._measure(d, ctx)


def _reply(rv, ctx):
    if rv["id"].startswith("task_"):
        ctx.setdefault("tasks", []).append(rv)
        return dict(ctx["task_answer"])
    return TF._reply(rv, ctx)


def walk(mod, st, ctx, limit=300):
    trace, measure, replies, user, res = [], {}, {}, {}, {}
    for _ in range(limit):
        res = mod.step(st, measure, replies, user)
        st = json.loads(json.dumps(res.pop("state"), ensure_ascii=False))
        trace.append((res["status"], st.get("phase"), tuple(d["cmd"] for d in res.get("do") or []), tuple(r["id"] for r in res.get("review") or [])))
        measure, replies, user = {}, {}, {}
        if res["status"] in ("done", "stop"):
            break
        if res["status"] == "execute":
            measure = {d["id"]: _measure(d, ctx) for d in res["do"]}
        elif res["status"] in ("review", "reject"):
            replies = {r["id"]: _reply(r, ctx) for r in res["review"]}
        elif res["status"] == "wait_user":
            user = {"approve": True}
    return trace, res, st


@pytest.fixture(autouse=True)
def _no_heavy(monkeypatch):
    monkeypatch.setattr(F, "audit_script", lambda st, S, M: {"ok": True})
    yield


def _start():
    return F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid")


def test_stuck_goes_to_maker_task_and_retry_really_reruns():
    ctx = {"bench_fail": 2, "task_answer": {"action": "retry", "note": "받기 실패는 잠깐 — 다시"}, "dims": {"BENCH1": (1080, 1920), "PEER1": (1080, 1920)},
           "span_src": "BENCH1.mp4", "cut_src": "BENCH1.mp4",
           "bench": {"id": "BENCH1", "title": "Skincare WHAT?!", "channel": "MissDarcei", "date": "20250627", "dur": 30, "sheet": "bench/sheet.jpg", "lines": []}}
    tr, res, st = walk(F, _start(), ctx)
    assert res["status"] == "done", tr[-4:]
    assert not any(t[0] == "stop" for t in tr)                    # 회원에게 묻지 않았다
    assert ctx["bench_calls"] == 3                                 # 1(실패) → 스스로 1(실패) → 과제 retry → 성공
    ask = ctx["tasks"][0]["ask"]
    assert "제작자" in ask and "영상 확인" in ask and "[가이드 01_소재.md 발췌]" in ask and '"action"' in ask


def test_task_limit_then_member():
    ctx = {"bench_fail": 99, "task_answer": {"action": "retry", "note": "다시"}}
    tr, res, st = walk(F, _start(), ctx)
    assert res["status"] == "stop" and len(ctx["tasks"]) == F.TASK_PER_KEY
    assert res.get("retry_ok")                                      # 회원에게는 쉬운 선택지(다시 시도)
    again = F.step(st, {}, {}, {})                                  # 상태만 다시 물어도 과제로 또 돌리지 않는다
    assert again["status"] == "stop" and not again.get("review")


def test_end_answer_stops_for_member():
    ctx = {"bench_fail": 99, "task_answer": {"action": "end", "note": "이 영상은 받을 수 없음"}}
    tr, res, st = walk(F, _start(), ctx)
    assert res["status"] == "stop" and len(ctx["tasks"]) == 1


def test_final_and_setup_stops_skip_task():
    st = _start()
    e = F._Stop("의약품·의료기기는 만들 수 없는 소재예요", "이 소재는 여기서 마칠게요", final=True)
    assert F._task(st, e, "bench_got", "bench") is None
    e2 = F._Stop("키 없음", "설정에서 넣어 주세요", retry="setup", ask_member=True)
    assert F._task(st, e2, "setup_check", "setup") is None
    e3 = F._Stop("영상을 받지 못했어요", "잠시 뒤", retry="bench")
    assert F._task(st, e3, "bench_got", "bench")["id"] == "task_1"


def test_give_origin_url_uses_given_origin_path():
    st = _start()
    st.update({"phase": "task_got", "read": {"product_words": ["크림"]}, "_task": {"id": "task_1", "why": "원본을 못 찾았어요", "fix": "", "retry": "titles",
                                                                                   "origin_missing": True, "stage": "origin"}})
    st["fmt"] = "연예인형"
    res = F.step(st, {}, {"task_1": {"action": "give", "origin_url": "https://www.youtube.com/watch?v=ABCDEFGHIJK", "note": "본인 채널"}}, {})
    assert [d["cmd"] for d in res.get("do") or []] == ["origin_probe"] and res["do"][0]["ids"] == ["ABCDEFGHIJK"]


def _head_flow():
    r = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:tools/calcopy/hybrid/flow.py"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 or "def _task(" in r.stdout:
        return None
    mod = types.ModuleType("flow_head")
    mod.__file__ = str(ROOT / "tools/calcopy/hybrid/flow.py")
    exec(compile(r.stdout, "flow_head.py", "exec"), mod.__dict__)
    mod.audit_script = lambda st, S, M: {"ok": True}
    return mod


def test_old_flow_asked_member_directly():
    """사보타주 기준 — 옛 flow 는 받기 실패 두 번이면 바로 회원에게 '다시 시도'(제작자 과제 없음)."""
    old = _head_flow()
    if old is None:
        pytest.skip("HEAD 가 이미 새 길")
    ctx = {"bench_fail": 2, "task_answer": {"action": "retry"}}
    tr, res, st = walk(old, old.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "stop" and "tasks" not in ctx
