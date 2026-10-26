# -*- coding: utf-8 -*-
"""관제263 10-26 잇템로그 회원 실측(98 #161) — 해외 원본 자동(렌즈)이 못 찾으면 회원 Claude 가 목표+가이드+도구로 직접 찾는다.
옛 길: 렌즈 후보 판정 0 → '해외 원본을 못 찾았어요 — 다시 시도를 누르시면 다른 방법으로' 멈춤 → 다시 시도(retry=of_got)는
같은 렌즈 후보를 다시 판정할 뿐(실행기 0회) → 회원은 다시 시도만 무한히 누른다(실측 3번).
새 길: f_of_find(review of_find: urls·queries) → 실행기 origin_foreign mode find(메타·썸네일·쇼츠 검색) → 같은 영상 판정(of_judge, 결과 검사 그대로)
→ 불합격이면 이유를 들고 다음 바퀴(F_FIND_MAX) → 한도 다 쓰면 그때만 회원에게 묻고, 다시 시도 = 회원 Claude 찾기 한 바퀴 더."""
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

BENCH = {"id": "BENCH1", "title": "치아 미백 테이프 이거 맞아??!", "channel": "잇템로그", "date": "20250801", "dur": 28, "sheet": "bench/sheet.jpg", "lines": []}


def _ctx(judge_ok_after: int | None):
    """judge_ok_after = 회원 찾기 몇 바퀴째 판정부터 '같음'인지(None = 끝까지 아님). 렌즈 판정은 늘 '아님'."""
    return {"ref_kind": "korean_reedit", "dims": {"ORIGX123456": (1080, 1920)}, "span_src": "ORIGX123456.mp4", "cut_src": "ORIGX123456.mp4",
            "bench": BENCH, "judge_ok_after": judge_ok_after, "find_round": 0}


def _measure(d, ctx):
    if d["cmd"] == "origin_foreign":
        ctx.setdefault("of_calls", []).append((d.get("mode"), tuple(d.get("urls") or ()), tuple(d.get("queries") or ())))
        if d.get("mode") == "lens":
            return {"mode": "lens", "cands": [{"n": 1, "platform": "ig", "id": "IGX", "title": "Video by someone", "korean": True}], "sheets": ["origin_foreign/judge_0.jpg"]}
        return {"mode": d.get("mode"), "cands": [{"n": 1, "platform": "yt", "id": "ORIGX123456", "title": "Purple whitening strips?!", "channel": "Joe",
                                                  "channel_id": "UCJOE", "date": "20250301", "dur": 20, "korean": False}],
                "sheets": ["origin_foreign/judge_0.jpg"]}
    return TF._measure(d, ctx)


def _reply(rv, ctx):
    i = rv["id"]
    if i == "of_find":
        ctx["find_round"] += 1
        ctx.setdefault("find_asks", []).append(rv["ask"])
        return {"urls": ["https://www.youtube.com/shorts/ORIGX123456"], "queries": ["purple teeth whitening strips reaction"], "why": "보라색 테이프 남성 컷"}
    if i == "of_judge":
        k = ctx.get("judge_ok_after")
        ok = k is not None and ctx["find_round"] >= k
        return {"same": [1] if ok else [], "why": "같은 촬영분" if ok else "다른 사람·다른 촬영"}
    return TF._reply(rv, ctx)


def walk(mod, st, ctx, limit=300, user_at_stop=None):
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


def test_lens_miss_member_finds_and_result_check_passes():
    ctx = _ctx(judge_ok_after=1)
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "done", tr[-4:]
    modes = [c[0] for c in ctx["of_calls"]]
    assert modes[:2] == ["lens", "find"]                                       # 렌즈 먼저 1번, 그다음 회원 Claude 가 찾은 것
    assert ctx["of_calls"][1][1] == ("https://www.youtube.com/shorts/ORIGX123456",)
    assert st["origins"][0]["id"] == "ORIGX123456"
    assert not any(t[0] == "stop" for t in tr)                                  # 회원에게 '다시 시도'를 묻지 않았다
    ask = ctx["find_asks"][0]
    assert "해외 원본 영상의 주소" in ask and "자동 검색 후보 없음" not in ask and "## 5." in ask   # 목표 + 가이드(브리프 §5) + 앞 결과


def test_failed_check_carries_reason_to_next_round():
    ctx = _ctx(judge_ok_after=2)
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "done", tr[-4:]
    assert ctx["find_round"] == 2
    assert "다른 사람·다른 촬영" in ctx["find_asks"][1]                           # 불합격 이유를 들고 다음 바퀴


def test_limit_then_ask_member_and_retry_really_runs():
    ctx = _ctx(judge_ok_after=None)
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "stop"
    assert ctx["find_round"] == F.F_FIND_MAX
    assert "원본 영상 주소를 알려 주시면" in json.dumps(res, ensure_ascii=False)
    n_calls = len(ctx["of_calls"])
    # 다시 시도 = 회원 Claude 찾기 한 바퀴 더 — 실제로 질문이 나가고 실행기가 돈다(옛 길: 같은 후보 재판정만, 실행기 0회)
    res2 = F.step(st, {}, {}, {"retry": True})
    st2 = res2.pop("state")
    assert [r["id"] for r in res2.get("review") or []] == ["of_find"], res2.get("status")
    res3 = F.step(st2, {}, {"of_find": _reply({"id": "of_find", "ask": ""}, ctx)}, {})
    assert [d["cmd"] for d in res3.get("do") or []] == ["origin_foreign"] and res3["do"][0]["mode"] == "find"
    assert n_calls == 1 + F.F_FIND_MAX


def _head_flow():
    r = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:tools/calcopy/hybrid/flow.py"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 or "f_of_find" in r.stdout:
        return None
    mod = types.ModuleType("flow_head")
    mod.__file__ = str(ROOT / "tools/calcopy/hybrid/flow.py")
    exec(compile(r.stdout, "flow_head.py", "exec"), mod.__dict__)
    mod.audit_script = lambda st, S, M: {"ok": True}
    return mod


def test_old_flow_stopped_and_retry_did_nothing():
    """사보타주 기준 — 옛 flow 는 렌즈 판정 0이면 멈추고, 다시 시도해도 실행기를 안 돌린다(이 시험 묶음이 그 결함을 잡는지)."""
    old = _head_flow()
    if old is None:
        pytest.skip("HEAD 가 이미 새 길")
    ctx = _ctx(judge_ok_after=1)
    tr, res, st = walk(old, old.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "stop" and "find_asks" not in ctx
    res2 = old.step(st, {}, {}, {"retry": True})
    assert not res2.get("do")                                                     # 실행기 0회 — 같은 렌즈 후보 판정만 다시
