# -*- coding: utf-8 -*-
"""runbatch.sh 두 번(전/후) 결과를 편마다 나란히: 자막 띠·극성·구간 수, 바뀐 편에 **변화**.

    PYTHONUTF8=1 py tools/calcopy/engine/analyze4_check/cmp.py <전 접두> <후 접두> [목록.txt]
(접두 = runbatch.sh 의 출력접두. 목록을 주면 그 순서로)
"""
from __future__ import annotations

import glob
import json
import sys


def load(prefix: str) -> dict:
    d = {}
    for f in glob.glob(prefix + ".*.jsonl"):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            d[r["vid"]] = r
    return d


def main() -> None:
    B, N = load(sys.argv[1]), load(sys.argv[2])
    order = ([l.strip().replace("\\", "/").split("/")[-1][:-4] for l in open(sys.argv[3], encoding="utf-8") if l.strip()]
             if len(sys.argv) > 3 else sorted(set(B) | set(N)))
    f = lambda r: f"{r['caption'].get('band')} {r['caption'].get('ink')} n={r['n_spans']}"
    for v in order:
        b, n = B.get(v), N.get(v)
        if not b or not n:
            continue
        same = (b["caption"].get("band"), b["caption"].get("ink"), b["n_spans"]) == (n["caption"].get("band"), n["caption"].get("ink"), n["n_spans"])
        print(f"{v[:11]:11} | {f(b):34} | {f(n):34}{'' if same else ' **변화**'}")


if __name__ == "__main__":
    main()
