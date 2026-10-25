# -*- coding: utf-8 -*-
"""VMake 보낸 초 검사(관제 270, 사장님 10-26 "장면 편집 뒤 자막 있는 컷만") — 결과물 검사 도구.

job 폴더마다 vmake_sent.json(업체로 넘긴 파일·초·허용 초, mix_pipeline._vmake_clean 이 보내기 직전에 쓴다)을 읽어
  보낸 초 > 허용 초(= 보낼 컷 합, vmake_send_cuts) + VMAKE_SENT_TOL 인 줄을 찾는다. 판정은 mix_pipeline.vmake_sent_check 한 곳.

    py shopping_shorts/scripts/vmake_sent_check.py --root shopping_shorts/data/mix_jobs [--since 2026-10-26]
    py shopping_shorts/scripts/vmake_sent_check.py --work <job 폴더>
종료 코드: 0 = 위반 0 · 1 = 위반 있음.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shopping_shorts.mix_pipeline import VMAKE_LEDGER, vmake_sent_check  # noqa: E402


def scan(dirs, since=""):
    rows, bad = 0, []
    for d in dirs:
        p = Path(d) / VMAKE_LEDGER
        if not p.exists():
            continue
        try:
            led = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            bad.append((Path(d).name, "-", f"장부를 못 읽음: {e!r}"))
            continue
        for r in led:
            if str(r.get("at") or "") < since:
                continue
            rows += 1
            for why in vmake_sent_check(r.get("sec"), r.get("allow")):
                bad.append((Path(d).name, r.get("kind"), why))
    return rows, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root")
    ap.add_argument("--work")
    ap.add_argument("--since", default="")
    a = ap.parse_args()
    dirs = [a.work] if a.work else [x for x in Path(a.root).iterdir() if x.is_dir()]
    rows, bad = scan(dirs, a.since)
    print(f"VMake 장부 {rows}줄 검사 · 위반 {len(bad)}")
    for job, kind, why in bad:
        print(f"  ✗ {job} [{kind}] {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
