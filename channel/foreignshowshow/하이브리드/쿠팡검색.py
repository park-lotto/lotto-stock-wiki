# -*- coding: utf-8 -*-
"""샥탬스토리 하이브리드 — 6편 제품을 쿠팡에서 찾는다(숏템메이커 coupang_search 그대로, 이 PC 회선 + 화면 뜨는 크롬).
선례 channel/hottemreport/현장썰하이브리드/쿠팡검색.py 와 같은 방식(검색어만 다름).

실행: py channel/foreignshowshow/하이브리드/쿠팡검색.py
결과: 같은 폴더 쿠팡검색_<날짜>.json
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["COUPANG_SEARCH_ENABLED"] = "1"   # 이 실행에서만 켠다(config 는 안 바꿈)
os.environ["COUPANG_PROXY"] = ""             # 직결 = 이 PC 주거용 회선

from shopping_shorts import coupang_search as cs  # noqa: E402

QUERIES = {
    "1 STORMBAG": ["스톰백 물막이", "흡수 팽창 모래주머니", "물에 부푸는 수해 방지 모래주머니"],
    "2 Squatty Potty": ["스쿼티포티", "변기 발판 쾌변", "Squatty Potty"],
    "3 Drop Stop": ["드롭스탑", "자동차 시트 틈새 쿠션", "Drop Stop 틈새"],
    "4 Spikeball": ["스파이크볼", "라운드넷 게임 세트"],
    "5 Bala Bangles": ["발라 뱅글", "손목 발목 웨이트 링"],
    "6 LARQ": ["라크 보틀", "UV 살균 물병", "LARQ 퓨어비스", "LARQ UV"],
}

dst = Path(__file__).with_name(f"쿠팡검색_{time.strftime('%Y-%m-%d')}.json")
out = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
only = sys.argv[1:]          # 검색어 일부만 다시: py 쿠팡검색.py "스쿼티포티"
for ep, qs in QUERIES.items():
    for q in qs:
        if only and q not in only:
            continue
        if not only and (out.get(q) or {}).get("ok"):
            continue                      # 이미 받은 검색어는 건너뜀(다시 돌려도 덮지 않게)
        r = cs.search(q, limit=10)
        out[q] = {"ep": ep, **r}
        print(f"## {ep} · {q} · ok={r.get('ok')} {r.get('notice', '')}")
        for it in (r.get("items") or [])[:8]:
            print("   ", it.get("product_id"), "|", (it.get("name") or "")[:70], "|", it.get("price", ""), "|",
                  it.get("rating", ""), "| 광고" if it.get("is_ad") else "")
        dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(4)
print("저장:", dst)
