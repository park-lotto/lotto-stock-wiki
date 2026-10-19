# -*- coding: utf-8 -*-
"""쿠팡 상품 검색 = 숏템메이커 관리자에 등록된 쿠팡 파트너스 오픈API 키로 (관제 097, 2026-10-20).

사장님 10-20 "쿠팡은 쿠팡api 있으면 되는 거 아닌가, 숏템메이커 관리자에 등록돼 있는데".
이 PC 회선·크롬은 쿠팡이 막을 때가 있다(10-19 저녁~ 검색 ok=False·상품 페이지 403). 파트너스 API 는 IP 차단과 무관.
키는 서버 DB 에만 있다(로컬로 꺼내지 않는다) → 서버에서 shopping_shorts.coupang_partners.search_products 를 그대로 부른다
(판단 주인 = 그 함수 한 곳, 키 = app._coupang_member_key(관리자 owner_cid)).
돌려주는 것: 상품번호·상품명·가격·대표 이미지·로켓 여부(파트너스 검색 응답). ★상품평 글·리뷰 수는 API 에 없다.
한 번에 최대 10개(API 상한), 호출 한도가 있으니 검색어는 꼭 필요한 것만.

    PYTHONUTF8=1 py tools/calcopy/coupang_api_search.py <out.json> "<검색어>" ["<검색어>" …]
10-20 실측: '스크럽대디'·'문어빨판 휴대폰 거치대'·'코퍼카우 커피' ok, 같은 제품 상품번호가 나옴.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

KEY = r"C:\Users\CH\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem"
HOST = "shoppingshorts.duckdns.org"     # 서버 IP 는 바뀐다 — 도메인으로
_REMOTE = r'''
import json, sys
sys.path.insert(0, ".")
from shopping_shorts import app, keyctx, coupang_partners as cp
ak, sk = app._coupang_member_key(keyctx.owner_cid())
out = {}
for q in json.loads(sys.argv[1]):
    out[q] = cp.search_products(q, limit=10, access_key=ak, secret_key=sk) if ak else {"ok": False, "notice": "관리자 파트너스 키 없음", "items": []}
print("@@JSON@@" + json.dumps(out, ensure_ascii=False))
'''


def search(queries: list[str]) -> dict:
    cmd = ("cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env 2>/dev/null; set +a; "
           "timeout 120 /usr/bin/python3 -c " + _shq(_REMOTE) + " " + _shq(json.dumps(queries, ensure_ascii=False)))
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, f"ubuntu@{HOST}", cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    line = next((l for l in r.stdout.splitlines() if l.startswith("@@JSON@@")), None)
    if line is None:
        raise RuntimeError(f"서버 검색 실패 rc={r.returncode}: {(r.stderr or r.stdout)[-400:]}")
    return json.loads(line[len("@@JSON@@"):])


def _shq(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def main():
    out = Path(sys.argv[1]); qs = sys.argv[2:]
    res = search(qs)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for q, r in res.items():
        print(f"## {q} · ok={r.get('ok')} {r.get('notice', '')}")
        for it in r.get("items", [])[:6]:
            print("   ", it["product_id"], "|", it["name"][:50], "|", it.get("price", ""), "| 로켓" if it.get("is_rocket") else "")


if __name__ == "__main__":
    main()
