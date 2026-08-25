# -*- coding: utf-8 -*-
"""체험중인데 포인트가 0인 계정에 기준선(_trial_topup)까지 채운다 — 1회용 백필.

★왜: 가입 즉시 자동체험(2026-08-25)에 포인트 지급이 빠져 있어 체험중 계정들이 전부 0P였다.
   코드는 고쳤지만 **이미 가입한 사람들**은 그대로라 한 번 채워준다.
사용: python -m scripts.backfill_trial_points [--apply]   (기본은 미리보기)
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from shopping_shorts.app import DB_PATH, _trial_topup      # 기준선은 여기 한 곳
from shopping_shorts.store import Store
from shopping_shorts import points, pricing

apply = "--apply" in sys.argv
st = Store(DB_PATH)
now = int(datetime.now(timezone.utc).timestamp())
targets = []
for c in st.list_customers():
    if c["id"] == 0:
        continue
    live = (c.get("trial_ends_at") or 0) > now or (c.get("full_access_until") or 0) > now
    if not live:
        continue
    bal = pricing.to_display(points.balance(st, c["id"]))
    targets.append((c["id"], c.get("email") or c.get("username"), bal))

print(f"체험/전기능 유효 계정 {len(targets)}건")
for cid, who, bal in targets:
    if apply:
        got = _trial_topup(st, cid)
        print(f"  cid={cid} {who} {bal}P -> +{got}P")
    else:
        print(f"  cid={cid} {who} {bal}P")
if not apply:
    print("\n미리보기입니다. 실제 지급하려면 --apply")
