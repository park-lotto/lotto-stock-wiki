#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_tiers.py — 원자 DB(atoms.db) → stock_tiers.yaml 자동 생성.

종목별 원자 개수로 등급 산정:
  5개+   = hot   (다관점 풀 갱신 대상)
  2~4개  = watch (팩트 추적)
  0~1개  = static (보존만, yaml 미명시 → default_tier)

⚠️ created_at 윈도우 함정 회피: 현재 DB는 적재일이 몰려 있어 절대 개수 기준.
   추후 적재가 일별로 쌓이면 '최근 N일' 윈도우로 전환 검토(NEXT_SESSION).
"""
import sqlite3
import sys
from pathlib import Path
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "pipeline" / "atoms" / "atoms.db"
OUT = ROOT / "wiki" / "_schema" / "stock_tiers.yaml"
HOT, WATCH = 5, 2

c = sqlite3.connect(DB)
rows = c.execute(
    "SELECT asset, COUNT(*) FROM atoms "
    "WHERE asset_level='stock' AND asset IS NOT NULL AND asset!='' "
    "GROUP BY asset"
).fetchall()

hot = sorted([a for a, n in rows if n >= HOT])
watch = sorted([a for a, n in rows if WATCH <= n < HOT])

lines = [
    f"# 종목 등급 — atoms.db 자동 생성 ({date.today()}) by scripts/gen_tiers.py",
    f"# 기준: 원자 {HOT}개+ = hot / {WATCH}~{HOT - 1}개 = watch / 그 외 static(미명시)",
    "# ⚠️ 수동 편집은 다음 자동생성에서 덮어쓰임.",
    "",
    "hot:",
]
lines += [f'  - "{a}"' for a in hot]
lines += ["", "watch:"]
lines += [f'  - "{a}"' for a in watch]
lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"hot {len(hot)} · watch {len(watch)} → {OUT.relative_to(ROOT)}")
print("hot:", ", ".join(hot))
