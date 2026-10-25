# -*- coding: utf-8 -*-
"""진행 감시창 — 모델 토큰 0(사장님 10-26 "1분에 한 번씩은 진행되는지 토큰 부담 없이 반응만").

    py tools/progress_watch.py <진행 파일> [<진행 파일> ...] [--every 60]

진행 파일 두 가지를 읽는다(파일 하나마다 한 덩어리):
  · 줄 파일(.txt) — 배경 작업자가 'N/M 단계 완료 → 다음 중' 한 줄씩 덧붙이는 것 → 마지막 줄
  · flow_dev 로그(.out/.jsonl) — 회원 경로 시험 → 고객 화면에 뜨는 줄(N/13 단계 · 멈춤 이유/해결)
1분마다 '살아있음 HH:MM · 마지막 변화 n분 전'을 찍는다. 변화가 10분 넘게 없으면 ⚠ 를 붙인다(멈췄는지 볼 것).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

STALL_MIN = 10


def flow_lines(p: Path) -> list[str]:
    """flow_dev 로그 → 고객 화면 줄(회원 SKILL.md 13줄 규칙과 같은 꼴)."""
    stages, out = None, []
    for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(l)
        except Exception:  # noqa: BLE001 — 로그 사이 섞인 일반 출력은 건너뛴다
            continue
        if d.get("stages"):
            stages, out = d["stages"], []
        n_all = len(stages or [])
        if d.get("end") == "stop":
            n = (d.get("stage") or {}).get("no", "?")
            out += [f"{n}/{n_all} 멈춤: {d.get('why')}", f"      {d.get('fix')}"]
        elif d.get("end"):
            out.append(f"{n_all}/{n_all} 완성")
        elif d.get("msg") and not str(d["msg"]).startswith("멈춤"):
            cur = str(d["msg"]).split("→")[-1].strip().replace(" 중", "").replace(" 완료", "")
            n = stages.index(cur) + 1 if stages and cur in stages else "?"
            line = f"{n}/{n_all} {d['msg']}"
            if not out or out[-1] != line:
                out.append(line)
    return out[-2:] if out and "멈춤" in out[-2:][0] else out[-1:]


def read(p: Path) -> list[str]:
    if not p.exists():
        return ["(아직 진행 파일 없음)"]
    if p.suffix in (".out", ".jsonl"):
        return flow_lines(p) or ["(시작 전)"]
    ls = [x for x in p.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
    return ls[-1:] or ["(시작 전)"]


def main() -> None:
    args = sys.argv[1:]
    every = 60
    if "--every" in args:
        i = args.index("--every"); every = int(args[i + 1]); del args[i:i + 2]
    files = [Path(a) for a in args]
    if not files:
        print(__doc__); return
    os.system("")          # 윈도 콘솔 색 켜기
    last, changed = {}, {}
    while True:
        now = time.time()
        print(f"\033[94m── 살아있음 {time.strftime('%H:%M')} ──\033[0m")
        for f in files:
            cur = read(f)
            if last.get(f) != cur:
                last[f], changed[f] = cur, now
            age = int((now - changed[f]) / 60)
            warn = " ⚠ 오래 그대로 — 멈췄는지 확인" if age >= STALL_MIN else ""
            print(f"\033[96m[{f.parent.name if f.suffix in ('.out', '.jsonl') else f.stem}]\033[0m 마지막 변화 {age}분 전{warn}")
            for line in cur:
                print(f"  \033[94m{line}\033[0m")
        sys.stdout.flush()
        time.sleep(every)


if __name__ == "__main__":
    main()
