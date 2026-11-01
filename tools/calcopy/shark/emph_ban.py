# -*- coding: utf-8 -*-
"""샥탬스토리 강조색 금지색 관문 — 렌더 전에 대본.json emph 칸에 금지색이 남았나 센다 (관제 097, 2026-10-28, 98 #189 보탬).

왜: 26편 Blinger 1차 납품본에 손 칸(how=hand)으로 '빨강'을 넣은 칸이 분홍 벽지·금발·빨간 도구 위에 남았는데,
보고에는 '빨강·분홍·주황은 처음부터 파랑·초록·민트로 바꿨다'고 적었다(recolor 뒤 emph_hand 로 다시 빨강을 넣은 것을 안 셌다).
분홍·빨강 바탕이 많은 편은 빨강·분홍·주황 강조를 아예 쓰지 않는다(지휘 재검수 10-28) — 그 약속을 사람 기억이 아니라 이 검사로 지킨다.

    PYTHONUTF8=1 py tools/calcopy/shark/emph_ban.py <대본.json|편 폴더> [...] [--ban 빨강,분홍,주황]
    → 금지색 칸 목록 · 있으면 rc=1 (렌더·납품 전에 앞 대본과 뒤 대본 둘 다 넣는다)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_BAN = ("빨강", "분홍", "주황")


def banned(doc: Path, ban=DEFAULT_BAN) -> list[tuple[str, str, str, str]]:
    p = doc / "대본.json" if doc.is_dir() else doc
    S = json.loads(p.read_text(encoding="utf-8"))
    return [(L["id"], e.get("cap", ""), e.get("color", ""), e.get("how", "")) for L in (S.get("final") or {}).get("lines", [])
            for e in L.get("emph") or [] if e.get("color") in ban]


def main() -> int:
    args, ban = [], DEFAULT_BAN
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--ban":
            ban = tuple(x for x in next(it).split(",") if x)
        else:
            args.append(Path(a))
    if not args:
        print(__doc__)
        return 2
    bad = 0
    for d in args:
        rows = banned(d, ban)
        bad += len(rows)
        print(f"{d}: 금지색({'·'.join(ban)}) {len(rows)}칸" + "".join(f"\n  {r[0]} '{r[1]}' {r[2]}({r[3]})" for r in rows))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
