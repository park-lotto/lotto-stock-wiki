# -*- coding: utf-8 -*-
"""Claude 가 처음 낸 재료 답을 실제 계획 명령(runner_ops.c_plan)에 다시 넣어 숫자 반려를 센다 — Claude 를 다시 부르지 않으니 같은 답으로
코드 고치기 전후를 그대로 비교한다(10-27 사장님 '뿌리 수정 · 두더지 아니지'). 작업 폴더(구간 시험 _segN)의 doc 을 덮어쓴다 — 시험 산출물에만 쓴다.

    PYTHONUTF8=1 py -m tools.calcopy.hybrid.plan_replay <작업 폴더…> [--which first|last] [--out <json>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

KIND = [("A-B-A", r"A-B-A"), ("재사용", r"같은 장면 재사용|재사용"), ("멈춤", r"멈춘 그림|컷 멈춤"), ("사진", r"그림 컷 비중"),
        ("컷 중앙", r"cut_median|컷 중앙"), ("훅", r"훅 0\.1"), ("경계·전환", r"샷보다 길|장면 전환|원본 장면 경계|짧은 조각"),
        ("컷 길이", r"컷 길이 \d"), ("얼굴", r"얼굴"), ("글자", r"글자")]


def kind(x: str) -> str:
    return next((k for k, p in KIND if re.search(p, x)), "기타")


def replay(work: Path, which: str = "first") -> dict:
    from tools.calcopy.hybrid import runner_ops as R
    st = json.loads((work / "flow_state.json").read_text(encoding="utf-8"))
    st = st.get("state", st)
    v = st["version"]
    W = work / "job"
    answers = sorted((W / "reviews").glob("*script_*/answer.json"))
    if not answers:
        return {"work": str(work), "error": "대본 답 없음"}
    a = json.loads((answers[0] if which == "first" else answers[-1]).read_text(encoding="utf-8"))
    S, M = a.get("대본"), a.get("재료")
    if not isinstance(S, dict) or not isinstance(M, dict):
        return {"work": str(work), "error": "답 꼴 틀림"}
    from tools.calcopy.hybrid import flow as F
    S = json.loads(json.dumps(S))
    F.audit_script(st, S, M)                                      # 서버가 하는 형식 자동 정리(voice·글·제목)까지 같게
    M = F._prep_material(st, S, M)
    R.c_write_doc(W, {"files": {f"{v}/대본.json": S, f"{v}/재료.json": M}, "cand_dir": True})
    on = sorted(F._origin_names(st))
    out = R.c_plan(W, {"version": v, "origin_names": on, "other_faces": F._other_faces(st)})
    items = [x.strip() for x in re.split(r";\s|\s/\s", str(out.get("over") or "")) if len(x.strip()) > 6] + list(out.get("jumps") or [])
    return {"work": str(work), "n": len(items), "kinds": dict(Counter(kind(x) for x in items)), "items": [x[:200] for x in items],
            "cuts": out.get("cuts"), "error": out.get("error")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("works", nargs="+")
    ap.add_argument("--which", default="first")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    res, tot = [], Counter()
    for w in a.works:
        try:
            r = replay(Path(w), a.which)
        except Exception as e:  # noqa: BLE001 — 한 편 실패는 적고 다음
            r = {"work": w, "error": f"{type(e).__name__}: {e}"[:300]}
        res.append(r)
        tot.update(r.get("kinds") or {})
        print(json.dumps({k: r.get(k) for k in ("work", "n", "kinds", "error")}, ensure_ascii=False), flush=True)
    print("합계", dict(tot))
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
