"""원본 찾기만 돌린 편(flow_dev --stop-at f_product)들의 통계 — 사장님 10-27 "다음 소재 계속 이어서 통계 내 봐".

    py tools/calcopy/hybrid/of_stats.py <폴더> [<폴더> …]      (폴더 = flow_dev --work, 안에 run.log · job/reviews/)

편마다: 소재·구간 시간(받기·판독·원본 찾기·판정·원본 받기)·어느 칸이 원본을 확보했나(1 = 요청 소재, 2 = 함께 찾은 소재)·
칸별 오푸스 같은 영상 판정(같은 것 수·이유 한 줄)·재업로드 뺌·끝(stop_at 단계·분)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def _t(s: str) -> datetime:
    return datetime.strptime(s, "%H:%M:%S")


def one(R: Path) -> dict:
    rows = []
    for ln in (R / "run.log").read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("{"):
            try:
                rows.append(json.loads(ln))
            except ValueError:
                pass
    calls = [r for r in rows if "call" in r]
    out = {"dir": R.name, "ref": "", "steps": {}, "won": None, "judge": {}, "end": None, "dups": None}
    for r in rows:
        if r.get("ref"):
            out["ref"] = r["ref"]
    # 구간: call(일 시작) → 다음 call 시각
    names = {"of_dual_b": "받기·판독", "of_dual": "원본 찾기·판정", "of_fetched": "원본 받기", "of_dedup": "재업로드 확인"}
    for a, b in zip(calls, calls[1:] + [None]):
        key = names.get(a.get("phase"), a.get("phase"))
        if a.get("do") and any(str(x).startswith("of") or x in ("origin_foreign",) for x in a["do"]):
            key = "원본 찾기(실행기)"
        elif a.get("review") and any("of_judge" in x for x in a["review"]):
            key = "같은 영상 판정(오푸스)"
        elif a.get("review") and any("ref_read" in x for x in a["review"]):
            key = "소재 판독(오푸스)"
        elif a.get("do") and "bench" in a["do"]:
            key = "소재 받기"
        end_t = (b or {}).get("t") or next((r["t"] for r in rows if r.get("end")), a["t"])
        out["steps"][key] = out["steps"].get(key, 0) + int((_t(end_t) - _t(a["t"])).total_seconds())
        if "함께 찾던" in str(a.get("msg")):
            out["won"] = 2
    if out["won"] is None and any(r.get("phase") == "of_fetched" for r in calls):
        out["won"] = 1
    for d in sorted((R / "job" / "reviews").glob("*of_judge*")):
        slot = "1" if "s1" in d.name else ("2" if "s2" in d.name else "-")
        try:
            a = json.loads((d / "answer.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out["judge"][slot] = {"same": len(a.get("same") or []), "why": str(a.get("why") or "")[:160]}
    for r in rows:
        if r.get("end"):
            out["end"] = {"phase": r.get("phase"), "min": r.get("min"), "end": r.get("end")}
        m = r.get("measure") or {}
        if "dups" in m:
            out["dups"] = m["dups"]
    return out


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    res = [one(Path(a)) for a in argv if (Path(a) / "run.log").exists()]
    for r in res:
        print(f"■ {r['dir']}  끝 {r['end']}  원본 확보 칸 {r['won']}")
        print("   시간 " + " · ".join(f"{k} {v}초" for k, v in r["steps"].items()))
        for s, j in sorted(r["judge"].items()):
            print(f"   칸{s} 판정 같은 것 {j['same']}개 — {j['why']}")
    done = [r for r in res if r["end"] and r["end"].get("end") == "stop_at"]
    if done:
        of = [r["steps"].get("원본 찾기(실행기)", 0) for r in done]
        print(f"\n합계 {len(res)}편 · 원본 확보 {len(done)}편 · 요청 소재(칸1)로 {sum(1 for r in done if r['won'] == 1)}편 · 함께 찾은 소재(칸2)로 {sum(1 for r in done if r['won'] == 2)}편"
              f" · 원본 찾기 실행기 평균 {sum(of) / len(of):.0f}초 · 끝까지 평균 {sum(float(r['end']['min']) for r in done) / len(done):.1f}분")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
