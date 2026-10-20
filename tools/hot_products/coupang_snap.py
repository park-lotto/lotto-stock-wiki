"""쿠팡 베스트 스냅샷 — 쿠팡파트너스 API(서버 키)로 카테고리 베스트 20위 ×13 + 골드박스. 쿠팡은 순위만 준다(판매수 없음).
서버에서 실행해 표준출력으로 JSON 을 내고, PC 가 work/snaps 에 snap.py 와 같은 꼴로 저장한다:
  ssh … 'cd ~/hot_research/hot_products && sudo -E bash -c "set -a; . /etc/shopping-shorts.env; set +a; PYTHONPATH=/home/ubuntu/lotto-stock-wiki python3 coupang_snap.py"' > work/snaps/cp_YYYYMMDD_HHMM.json
키는 서버 밖으로 나가지 않는다(값을 출력하지 않음)."""
import json, sys, time
from shopping_shorts import keyroute, coupang_partners as cp
from shopping_shorts.app import DB_PATH, Store

CATS = {"1010": "뷰티", "1011": "출산/유아동", "1013": "주방용품", "1014": "생활용품", "1015": "홈인테리어", "1016": "가전디지털",
        "1017": "스포츠/레저", "1018": "자동차용품", "1029": "반려동물용품", "1001": "여성패션", "1002": "남성패션", "1012": "식품", "1024": "헬스/건강식품"}
keys, _ = keyroute.keys_for(Store(DB_PATH), 0, keyroute.SVC_COUPANG); ak, sk = cp.split_key(keys[0])
out = {"ts": time.strftime("%Y%m%d_%H%M"), "at": time.time(), "items": []}
def add(lst, d):
    for x in d.get("data") or []:
        pid = x.get("productId")
        out["items"].append({"site": "coupang", "list": lst, "rank": x.get("rank"), "id": f"coupang:{pid}", "title": x.get("productName", ""),
                             "img": x.get("productImage", ""), "price": f"{int(x.get('productPrice') or 0):,}원",
                             "url": f"https://www.coupang.com/vp/products/{pid}", "m": {"rocket": x.get("isRocket")}, "ad": False})
for cid, nm in CATS.items():
    s, d = cp._call("GET", cp._API_BASE + f"/products/bestcategories/{cid}?limit=20", ak, sk)
    if s != 200: print(f"★쿠팡 {nm} {s}", file=sys.stderr)
    add(nm, d if s == 200 else {})
s, d = cp._call("GET", cp._API_BASE + "/products/goldbox", ak, sk)
add("골드박스", d if s == 200 else {})
print(json.dumps(out, ensure_ascii=False))
print(f"쿠팡 {len(out['items'])}개", file=sys.stderr)
