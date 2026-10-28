# -*- coding: utf-8 -*-
"""클로드형 라이선스 키 발급(개발·시험용, 관제 234) — 페이지 '키 발급' 버튼과 같은 함수(claude_portal.issue_license)를 부른다.

키 원문은 화면에 찍지 않고 --out 파일에만 쓴다(0600). 비밀값은 서버와 같아야 한다(env CLAUDE_LICENSE_SECRET 또는 DASH_SECRET).

    py tools/claude_portal/issue_key.py --db <reference.db> --cid 0 --out <키 파일>
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--cid", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    from shopping_shorts import claude_portal as cp
    from shopping_shorts.store import Store
    got = cp.issue_license(a.cid, Store(a.db))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(got["key"], encoding="utf-8")
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    print(f"발급: cid {a.cid} · kv {got['kv']} · 만료 {got['expires']} → {out} (원문은 파일에만)")


if __name__ == "__main__":
    main()
