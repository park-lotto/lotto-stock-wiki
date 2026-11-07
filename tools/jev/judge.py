# -*- coding: utf-8 -*-
r"""Jev 판단기 — CLAUDE.md 0원칙 도구.

사용: ~\jev-lab\.venv\Scripts\python -X utf8 tools\jev\judge.py 질문.json [--dry]
     정본 = 저장소 tools/jev/judge.py 한 벌(모든 PC 공용). jev-lab 폴더엔 SDK 가상환경·.env 키만 둔다.
     고칠 때 커밋 트랙 = Jev도입 (관제 332)
질문.json = {"problem": 증상·증거, "facts": [확인한 사실], "causes": [후보 원인 2+],
            "fixes": [후보 해결책 2+], "where": [이 판단이 적힌 곳 — grep 으로 찾은 파일:함수 전부],
            "images": {이름: 경로}?}
출력(JSON): 원인마다 root·proven·oneline / 해결마다 fixroot·mole·backstep·risk / best_cause·best_fix(+confidence)
          + must4 = 필수 4항목 판정(2026-11-05 사장님 — 어떤 결정이든 반드시):
            ① 뿌리     best_cause 가 근본 뿌리 원인인가        root    ≥ 0.7
            ② 근본해결 best_fix 가 뿌리를 없애는가            fixroot ≥ 0.7
            ③ 한줄기   고친 뒤 그 판단이 주인 함수 한 줄기에만 남나 oneowner ≥ 0.7
                       (원인 쪽 oneline 은 참고 — 낮거나 where 2곳+ 면 '여러 벌' 경고)
            ④ 두더지X  best_fix 가 두더지잡기가 아닌가          mole    ≤ 0.3
            넷 다 통과해야 verdict="통과". 하나라도 아니면 "보류" — 더 재서 다시 묻는다.
키: 환경변수 TYPESAFE_API_KEY → 없으면 ~/jev-lab/.env (저장소에 키를 두지 마라)
--dry: 질문 꼴만 출력(키 없이 점검)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from typesafe_sdk import Choice, Image, Noul, TypeSafeClient

HERE = Path(__file__).resolve().parent


def _load_env() -> None:
    # 키는 저장소에 두지 않는다 — PC마다 ~/jev-lab/.env 에서 읽는다(TheRose·CH 둘 다 홈 아래 jev-lab)
    for env in (Path.home() / "jev-lab" / ".env", HERE / ".env"):
        if not env.exists():
            continue
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


ROOT_OK, FIX_OK, ONELINE_OK, MOLE_MAX = 0.7, 0.7, 0.7, 0.3


def build(q: dict):
    causes, fixes = list(q.get("causes") or []), list(q.get("fixes") or [])
    where = [str(w).strip() for w in (q.get("where") or []) if str(w).strip()]
    # ★필수 4항목은 원인·해결 둘 다 있어야 잴 수 있다 — 한쪽만 묻는 결정은 받지 않는다
    if len(causes) < 2 or len(fixes) < 2:
        raise SystemExit("필수: causes 2개 이상 AND fixes 2개 이상(내가 하려는 것 + 대안)")
    if not where:
        raise SystemExit("필수: where — 이 판단이 적힌 곳(파일:함수)을 grep 으로 전부 찾아 적어라. 한줄기인지 재려면 있어야 한다")
    state = {"problem": q["problem"], "facts": list(q.get("facts") or []), "where": where}
    state |= {f"cause_{i}": c for i, c in enumerate(causes)}
    state |= {f"fix_{i}": f for i, f in enumerate(fixes)}
    Q = {}
    for i in range(len(causes)):
        Q[f"root_{i}"] = Noul(instructions=f"`cause_{i}` is the root cause of `problem` (not merely a symptom or a downstream effect)")
        Q[f"proven_{i}"] = Noul(instructions=f"The `facts` directly prove that `cause_{i}` is the cause of `problem` (not just consistent with it)")
        Q[f"oneline_{i}"] = Noul(instructions=f"`cause_{i}` comes from one single owner function / one code path (one line of logic), not from the same decision being written separately in several places of `where` that each must be fixed")
    for i in range(len(fixes)):
        Q[f"fixroot_{i}"] = Noul(instructions=f"`fix_{i}` removes the root cause of `problem` for all future cases (not a one-off patch, not adding another check on top of a broken one)")
        Q[f"oneowner_{i}"] = Noul(instructions=f"After `fix_{i}`, the decision behind `problem` is made in exactly one owner function that every path in `where` calls (one line of logic), not still written separately in several places")
        Q[f"mole_{i}"] = Noul(instructions=f"`fix_{i}` is whack-a-mole: it fixes only this occurrence or symptom, so the same defect can pop up again in another place of `where`, another input, or another form")
        Q[f"backstep_{i}"] = Noul(instructions=f"`fix_{i}` would have to be undone or redone later (a step backwards)")
        Q[f"risk_{i}"] = Noul(instructions=f"`fix_{i}` is likely to break something else that currently works")
    if len(causes) >= 2:
        Q["best_cause"] = Choice(instructions="Which candidate is the true root cause of `problem` given the `facts`",
                                 criteria={f"cause_{i}": c[:300] for i, c in enumerate(causes)} | {"none": "None of the candidates is the root cause"})
    if len(fixes) >= 2:
        Q["best_fix"] = Choice(instructions="Which candidate fix best removes the root cause of `problem` with the least risk",
                               criteria={f"fix_{i}": f[:300] for i, f in enumerate(fixes)} | {"none": "None of the candidate fixes removes the root cause"})
    assets = {k: Image(Path(v)) for k, v in (q.get("images") or {}).items()}
    return state, Q, assets, causes, fixes


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    q = json.loads(Path(args[0]).read_text(encoding="utf-8-sig"))
    state, Q, assets, causes, fixes = build(q)
    if "--dry" in sys.argv:
        print(json.dumps({"state": state, "questions": sorted(Q), "images": sorted(assets)}, ensure_ascii=False, indent=2))
        return
    _load_env()
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise SystemExit("TYPESAFE_API_KEY 없음 — 환경변수나 jev-lab\\.env 에 넣으세요")
    with TypeSafeClient(model="jev-latest", timeout=90.0) as cl:
        r = cl.system_one(state=state, questions=Q, assets=assets or None)
    a = r.answers
    n = lambda k: round(float(a[k].noul), 2)
    out = {
        "causes": [{"cause": c, "root": n(f"root_{i}"), "proven": n(f"proven_{i}"), "oneline": n(f"oneline_{i}")}
                   for i, c in enumerate(causes)],
        "fixes": [{"fix": f, "fixroot": n(f"fixroot_{i}"), "oneowner": n(f"oneowner_{i}"), "mole": n(f"mole_{i}"), "backstep": n(f"backstep_{i}"), "risk": n(f"risk_{i}")}
                  for i, f in enumerate(fixes)],
    }
    idx = {}
    for key, items in (("best_cause", causes), ("best_fix", fixes)):
        if key in a:
            ch = a[key].choice
            idx[key] = None if ch == "none" else int(str(ch).split("_")[1])
            out[key] = {"pick": None if idx[key] is None else items[idx[key]],
                        "confidence": round(float(a[key].confidence), 2)}
    out["must4"] = must4(out, idx.get("best_cause"), idx.get("best_fix"), len(state["where"]))
    print(json.dumps(out, ensure_ascii=False, indent=2))


def must4(out: dict, ci, fi, n_where: int) -> dict:
    """필수 4항목 — best 후보 기준. 하나라도 미달이면 보류(결정·말·커밋 금지, 더 재서 다시 묻는다)."""
    c = out["causes"][ci] if ci is not None else None
    f = out["fixes"][fi] if fi is not None else None
    items = {
        "①뿌리원인": (c is not None and c["root"] >= ROOT_OK, c and c["root"], f"root ≥ {ROOT_OK}"),
        "②근본해결": (f is not None and f["fixroot"] >= FIX_OK, f and f["fixroot"], f"fixroot ≥ {FIX_OK}"),
        # ③ = 고친 뒤 그 판단이 주인 함수 한 줄기에만 남는가(해결책 기준). 원인이 여러 벌(oneline 낮음)이면 모으는 수리여야 통과한다
        "③한줄기": (f is not None and f["oneowner"] >= ONELINE_OK, f and f["oneowner"], f"oneowner ≥ {ONELINE_OK}"),
        "④두더지아님": (f is not None and f["mole"] <= MOLE_MAX, f and f["mole"], f"mole ≤ {MOLE_MAX}"),
    }
    res = {k: {"ok": bool(ok), "value": v, "need": need} for k, (ok, v, need) in items.items()}
    fails = [k for k, r in res.items() if not r["ok"]]
    if ci is None:
        fails.append("best_cause=none(후보 중 뿌리 없음)")
    if fi is None:
        fails.append("best_fix=none(뿌리를 없애는 해결책 없음)")
    res["where_count"] = n_where
    res["cause_oneline"] = c and c["oneline"]   # 원인이 지금 한 줄기인가(참고) — 낮으면 여러 벌이 뿌리
    if n_where > 1 or (c is not None and c["oneline"] < ONELINE_OK):
        res["warn"] = f"같은 판단이 {n_where}곳에 적혀 있다(원인 한줄기 {c and c['oneline']}) — 한 곳만 고치면 두더지잡기, 주인 함수로 모으는 수리여야 한다"
    res["verdict"] = "통과" if not fails else "보류"
    res["fails"] = sorted(set(fails))
    return res


if __name__ == "__main__":
    main()
