"""완주 점검 — 편(회원 시험·관리자 개발 실행) 전체의 실행 기록을 한 번에 훑어 느린 단계·실패·되돌아감을 뽑는다(사장님 10-27
"내가 체크해 보라고 해야 다 찾나 — 진행되는 작업들 이런 거 엄청 많을 텐데"). 편을 하나씩 눈으로 보지 않는다.

쓰는 법:  py tools/calcopy/hybrid/run_audit.py <폴더> [<폴더> …]
    폴더 아래 runner.log(회원 시험: home/창고/flow/<sid>/runner.log)·flow_log.jsonl(관리자 flow_dev)을 모두 찾는다.
읽는 것:
    runner.log  '[runner] <cmd> <초>s ok|ERR …'      → 단계 시간·실패 · 'ok HOLLOW …' = 결과가 비었거나 일부를 버린 조용한 실패(runner_ops.hollow)
    flow.json   message 의 '다시 …(n/m): <이유>'      → 되돌아감(반려) 이유
    flow_log.jsonl msg 줄                             → 같은 꼴(관리자)
기준: SLOW = 한 번에 이 초 넘는 실행기 일(원본 찾기·렌더 같은 긴 일은 LONG_OK 안이면 느림 아님)."""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SLOW = 180          # 실행기 한 일이 이보다 오래 걸리면 '느림'
LONG_OK = {"render": 900, "plan": 420, "clean_text": 600, "origin_foreign": 300, "bench": 120, "origin_get": 180, "check": 600}
RUN = re.compile(r"\[runner\] (\S+) ([\d.]+)s (ok|ERR)(.*)")
HOL = re.compile(r"HOLLOW (.+)$")
REDO = re.compile(r"다시 [^(]*\((\d+)/(\d+)\): (.+)$")


def runs(roots: list[Path]) -> list[tuple[str, Path]]:
    out = []
    for r in roots:
        for f in r.rglob("runner.log"):
            out.append((str(f.parent.relative_to(r.parent)), f.parent))
        for f in r.rglob("flow_log.jsonl"):
            out.append((str(f.parent.relative_to(r.parent)), f.parent))
    return sorted(set(out))


def audit(name: str, d: Path) -> dict:
    steps, errs, slow, hollow = [], [], [], []
    rl = d / "runner.log"
    if rl.exists():
        for ln in rl.read_text(encoding="utf-8", errors="replace").splitlines():
            m = RUN.search(ln)
            if not m:
                continue
            cmd, sec, ok, rest = m.group(1), float(m.group(2)), m.group(3), m.group(4).strip()
            steps.append((cmd, sec, ok))
            if ok == "ERR":
                errs.append(f"{cmd} {sec:.0f}초 {rest[:120]}")
            hm = HOL.search(rest)
            if ok == "ok" and hm:
                hollow.append(f"{cmd} {hm.group(1)[:140]}")
            if sec > max(SLOW, LONG_OK.get(cmd, 0)):
                slow.append(f"{cmd} {sec:.0f}초")
    redo = Counter()
    msgs = []
    fj = d / "flow.json"
    if fj.exists():
        msgs.append(str(json.loads(fj.read_text(encoding="utf-8")).get("message") or ""))
    fl = d / "flow_log.jsonl"
    if fl.exists():
        for ln in fl.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                msgs.append(str(json.loads(ln).get("msg") or ""))
            except ValueError:
                pass
    last = None
    for m in msgs:
        r = REDO.search(m)
        if r and m != last:
            redo[r.group(3).strip()] += 1
        last = m
    stage = ""
    if fj.exists():
        sg = json.loads(fj.read_text(encoding="utf-8")).get("stage") or {}
        stage = f"{sg.get('no')}/{sg.get('total')} {sg.get('text')}"
    tot = sum(s for _, s, _ in steps)
    by = defaultdict(float)
    for c, s, _ in steps:
        by[c] += s
    return {"name": name, "stage": stage, "total_sec": round(tot), "top": sorted(by.items(), key=lambda kv: -kv[1])[:4],
            "errs": errs, "slow": slow, "hollow": hollow, "redo": redo}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    roots = [Path(a) for a in argv] or [Path("C:/숏템_칼카피")]
    rows = [audit(n, d) for n, d in runs(roots)]
    allredo = Counter()
    for r in rows:
        allredo.update(r["redo"])
        print(f"■ {r['name']}  [{r['stage']}]  실행기 합 {r['total_sec']}초 · 큰 몫 " + ", ".join(f"{c} {s:.0f}초" for c, s in r["top"]))
        for e in r["errs"]:
            print(f"   ✗ 실패  {e}")
        for h in r["hollow"]:
            print(f"   ⚠ ok인데 비어 있음  {h}")
        for s in r["slow"]:
            print(f"   ⏱ 느림  {s}")
        for k, n in r["redo"].most_common():
            print(f"   ↺ 되돌아감 {n}번  {k}")
    if allredo:
        print("\n되돌아감 이유 합계: " + " · ".join(f"{k} {n}" for k, n in allredo.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
