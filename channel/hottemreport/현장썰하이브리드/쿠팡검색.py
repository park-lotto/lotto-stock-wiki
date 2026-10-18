# -*- coding: utf-8 -*-
"""현장썰 하이브리드 — 5편 판매처를 쿠팡에서 찾는다(숏템메이커 coupang_search 그대로, 이 PC 회선 + 화면 뜨는 크롬).

실행: py channel/hottemreport/현장썰하이브리드/쿠팡검색.py
결과: 같은 폴더 쿠팡검색_2026-10-18.json
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # 윈도 콘솔 cp949 에서 '—' 등으로 죽지 않게
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["COUPANG_SEARCH_ENABLED"] = "1"   # 이 실행에서만 켠다(config 는 안 바꿈)
os.environ["COUPANG_PROXY"] = ""             # 직결 = 이 PC 주거용 회선

from shopping_shorts import coupang_search as cs  # noqa: E402

QUERIES = {
    "1 가짜잠자리": ["잠자리 모기 퇴치", "가짜 잠자리 모기"],
    "2 대용량물병": ["대용량 물병 4L", "4리터 물병 손잡이"],
    "3 전동신발": ["전동 롤러 신발", "전동 인라인 신발"],
    "4 미니카": ["유아 전동차 포르쉐", "미니 전동차 어린이"],
    "5 고양이집게": ["고양이 빵 봉지 클립", "고양이 봉지 집게"],
}

out = {}
for ep, qs in QUERIES.items():
    for q in qs:
        r = cs.search(q, limit=8)
        out[q] = {"ep": ep, **r}
        print(f"## {ep} · {q} · ok={r.get('ok')} {r.get('notice', '')}")
        for it in (r.get("items") or [])[:6]:
            print("   ", it.get("product_id"), "|", (it.get("name") or "")[:60], "|",
                  it.get("rating", ""), it.get("review_count", it.get("rating_count", "")))
dst = Path(__file__).with_name("쿠팡검색_2026-10-18.json")
dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("저장:", dst)
