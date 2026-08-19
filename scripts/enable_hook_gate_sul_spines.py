# -*- coding: utf-8 -*-
"""훅 3초 게이트를 유튜브 썰쇼핑 스파인에만 켠다(2026-08-19).

왜 스크립트인가: 손으로 SQL을 치면 어느 서버에 무엇을 켰는지 기록이 안 남고,
다시 켤 때 조건이 달라진다. 조건을 코드에 적어 한 곳에서만 정한다(0순위-B).

켜는 대상: fit_categories에 '오용형' 또는 '제품정체형'이 있는 승인 스파인.
  hook_3s      = 둘 다 (유튜브 = 완시청 장사)
  hook_conceal = '제품정체형'(은폐형)만 — 오용형은 정체를 처음부터 밝힌다.

실행: cd /home/ubuntu/lotto-stock-wiki && python3 scripts/enable_hook_gate_sul_spines.py [--apply]
      (--apply 없이는 무엇이 바뀔지 보여주기만 한다)
"""
import sys
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

from shopping_shorts.app import DB_PATH          # 라이브가 쓰는 DB를 그대로 쓴다
from shopping_shorts.store import Store

SUL = {"오용형", "제품정체형"}
apply_ = "--apply" in sys.argv

st = Store(DB_PATH)
print("DB:", DB_PATH)
for sp in st.list_spines(status="approved"):
    fits = set(sp.get("fit_categories") or [])
    if not (fits & SUL):
        continue
    conceal = "제품정체형" in fits
    print("  #%s %s | fit=%s → hook_3s=True, hook_conceal=%s (현재 %s/%s)" % (
        sp["id"], sp["name"], sorted(fits), conceal,
        sp.get("hook_3s"), sp.get("hook_conceal")))
    if apply_:
        st.set_spine_style(sp["id"], hook_3s=True, hook_conceal=conceal)
print("적용됨" if apply_ else "미적용(--apply를 붙여라)")
