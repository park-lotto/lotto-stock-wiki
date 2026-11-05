# -*- coding: utf-8 -*-
"""08 워커3 — 쿠팡 웹 검색(shopping_shorts.coupang_search, 이 PC 회선·화면 크롬)을 워커 전용 프로필로.
    PYTHONUTF8=1 py 쿠팡검색_w3.py <out.json> "<검색어>" …"""
import json, os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
os.environ["COUPANG_SEARCH_ENABLED"] = "1"
os.environ["COUPANG_PROXY"] = ""
from shopping_shorts import config, coupang_search as cs  # noqa: E402
config.COUPANG_PROFILE_DIR = str(ROOT / ".coupang_w3" / ".coupang_profile_search")
out = {}
for q in sys.argv[2:]:
    r = cs.search(q, limit=20)
    out[q] = r
    print(f"## {q} ok={r.get('ok')} {r.get('notice', '')}")
    for it in (r.get("items") or [])[:20]:
        print("   ", it.get("product_id"), "|", (it.get("name") or "")[:70], "|", it.get("rating", ""), it.get("review_count", it.get("rating_count", "")))
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
