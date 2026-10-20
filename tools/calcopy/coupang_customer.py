# -*- coding: utf-8 -*-
"""회원 PC 쿠팡 검색(사장님 10-21: 회원 본인 파트너스 키 — 없는 사람만 본인 PC 크롬). 서버 정보 없음(설치본 묶음에 들어간다).
판단 주인: 검색 = shopping_shorts.coupang_partners.search_products(서비스와 같은 함수) · 크롬 길 = hybrid/customer.coupang_chrome."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def search(queries: list[str]) -> dict:
    ak, sk = os.environ.get("COUPANG_ACCESS_KEY", ""), os.environ.get("COUPANG_SECRET_KEY", "")
    if os.environ.get("CALCOPY_DEV_COUPANG_SERVER") == "1" and not (ak and sk):
        # 개발 PC 시험 전용 — 이 PC 회선은 쿠팡이 막는다(10-21 실측 '사용권한이 제한된 페이지') → '키 있는 회원' 길을 서버 관리자 키로 흉내.
        #   coupang_api_search(서버 SSH)는 설치본에 없다 — 회원 PC 에서는 ImportError 로 이 줄이 돌 수 없다
        from tools.calcopy import coupang_api_search as srv
        os.environ.pop("CALCOPY_CUSTOMER_MODE", None)
        try:
            return srv.search(queries)
        finally:
            os.environ["CALCOPY_CUSTOMER_MODE"] = "1"
    if not (ak and sk):
        return {q: {"ok": False, "need": "chrome", "notice": "회원 파트너스 키 없음 — 크롬 검색", "items": []} for q in queries}
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from shopping_shorts import coupang_partners as cp
    return {q: cp.search_products(q, limit=10, access_key=ak, secret_key=sk) for q in queries}
