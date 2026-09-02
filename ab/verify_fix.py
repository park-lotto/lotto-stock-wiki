# -*- coding: utf-8 -*-
"""가설 검증 — 재픽 프롬프트가 `available`을 안 넘겨서 problem이 망가지는가.

프로덕션 코드를 **고치지 않고**, `_want_shots_for_role`을 잠깐 감싸(monkeypatch)
available을 주입한 상태로 같은 케이스를 돌려 비교한다.
→ 좋아지면 원인 확정. 그 다음에 진짜 코드를 고친다.
"""
import io, json, os, sys, time
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = r"C:/Users/CH/Desktop/로또의 주식"
sys.path.insert(0, _ROOT); sys.path.insert(0, _HERE)
os.chdir(_ROOT)
from shopping_shorts import edit_plan
from run_ab import load_job, score
from ab_repick import make_claude_call, make_gemini_call

LOG = os.path.join(_HERE, "logs_fix"); os.makedirs(LOG, exist_ok=True)
beats, seg_map = load_job()
AVAIL = {s.get("shot_role") for s in seg_map.values() if s.get("shot_role")}

_orig = edit_plan._want_shots_for_role

def patched(role, available=None):
    # 재픽 호출부(available 미전달)에 실제 재고를 주입한다.
    return _orig(role, available=available if available is not None else AVAIL)

def run(model, fixed, rep):
    cb = [dict(b, fit=1) for b in beats]
    base, _ = score(cb, seg_map)
    tag = "%s_%s_r%d" % (model, "fixed" if fixed else "orig", rep)
    call = (make_claude_call(model, LOG, tag) if model != "gemini"
            else make_gemini_call(LOG, tag))
    if fixed:
        edit_plan._want_shots_for_role = patched
    try:
        out = edit_plan._repick_weak_beats([dict(b) for b in cb], seg_map, call=call)
    finally:
        edit_plan._want_shots_for_role = _orig
    after, det = score(out, seg_map)
    prob = [d for d in det if d["role"] == "problem"]
    return {"model": model, "fixed": fixed, "rep": rep, "base": base, "after": after,
            "problem_bad": sum(1 for d in prob if d["mismatch"]),
            "problem_role": prob[0]["shot_role"] if prob else None,
            "detail": det}

rows = []
import sys as _s
REP = int(_s.argv[1]) if len(_s.argv) > 1 else 4
for rep in range(REP):
    for model in (_s.argv[2].split(",") if len(_s.argv) > 2 else ["opus", "gemini"]):
        for fixed in [False, True]:
            r = run(model, fixed, rep)
            rows.append(r)
            print("%-7s %-6s r%d  어긋남 %d→%d  problem결=%s %s"
                  % (model, "고침" if fixed else "원본", rep, r["base"], r["after"],
                     r["problem_role"], "BAD" if r["problem_bad"] else "ok"), flush=True)
            json.dump(rows, io.open(os.path.join(_HERE, "fix_results.json"), "w",
                                    encoding="utf-8"), ensure_ascii=False, indent=1)

print("\n=== 요약 ===")
for model in ["opus", "gemini"]:
    for fixed in [False, True]:
        rs = [r for r in rows if r["model"] == model and r["fixed"] == fixed]
        if rs:
            print("%-7s %-6s  평균 어긋남 %.2f  problem어긋남 %d/%d"
                  % (model, "고침" if fixed else "원본",
                     sum(r["after"] for r in rs) / len(rs),
                     sum(r["problem_bad"] for r in rs), len(rs)))
