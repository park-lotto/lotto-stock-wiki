# -*- coding: utf-8 -*-
"""서버 Jev 창구 — 회원 엔진의 결정(후보 고르기)은 여기서만 Jev 에 묻는다(관제 319 D7, 전역 0원칙).
키 = 서버 환경 TYPESAFE_API_KEY. 회원 묶음에 이 파일·키 이름이 들어가면 benchmark_pack.check 가 막는다."""
from __future__ import annotations

import os

try:
    from typesafe_sdk import Choice, Noul
except ImportError:  # 시험·SDK 없는 PC — 질문 꼴만 만든다(실제 호출은 _client 가 JevDown)
    def Choice(**kw): return {"type": "choice", **kw}
    def Noul(**kw): return {"type": "noul", **kw}

CONF_OK = 0.7


class JevDown(Exception):
    pass


def _client():
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise JevDown("no_key")
    try:
        from typesafe_sdk import TypeSafeClient
    except ImportError as e:
        raise JevDown("no_sdk") from e
    return TypeSafeClient(model="jev-latest", timeout=60.0)


def decide(problem: str, facts: list[str], fixes: list[str], client=None) -> dict:
    if len(fixes) < 2:
        raise ValueError("후보는 2개 이상")
    state = {"problem": problem, "facts": list(facts)} | {f"fix_{i}": f for i, f in enumerate(fixes)}
    Q = {f"fixroot_{i}": Noul(instructions=f"`fix_{i}` removes the root cause of `problem` for all future cases (not a one-off patch, not adding another check on top of a broken one)") for i in range(len(fixes))}
    Q["best_fix"] = Choice(instructions="Which candidate fix best removes the root cause of `problem` with the least risk",
                           criteria={f"fix_{i}": f[:300] for i, f in enumerate(fixes)} | {"none": "None of the candidate fixes removes the root cause"})
    own = client is None
    cl = _client() if own else client
    try:
        r = (cl.__enter__() if own else cl).system_one(state=state, questions=Q)
    except JevDown:
        raise
    except Exception as e:  # noqa: BLE001 — 결정 없이 넘어가지 않는다: 부르는 쪽이 멈춘다
        raise JevDown(type(e).__name__) from None
    finally:
        if own:
            cl.__exit__(None, None, None)
    try:
        a = r.answers
        best = a["best_fix"]
        pick = None if best.choice == "none" else int(str(best.choice).split("_")[1])
        conf = round(float(best.confidence), 2)
        fixroot = [round(float(a[f"fixroot_{i}"].noul), 2) for i in range(len(fixes))]
    except Exception:  # noqa: BLE001 — 답 모양이 이상하면 결정 없이 멈춘다
        raise JevDown("bad_answer") from None
    if pick is not None and not (0 <= pick < len(fixes)):
        pick = None
    return {"pick": pick, "conf": conf, "fixroot": fixroot,
            "ok": pick is not None and conf >= CONF_OK}
