"""사장님이 판정 페이지에서 찍은 영상 카테고리를 지정하고, 지금 랭킹에도 바로 반영한다.

  python3 -m scripts.apply_category_overrides 제품정체형 id1,id2,...
  python3 -m scripts.apply_category_overrides "" id1          # 지정 해제

지정값은 category_overrides에 남아 **이후 모든 수집 저장 때** 판정기를 이긴다
(store._apply_overrides — 저장 자리 한 곳에서만 덮는다).
"""
import json
import sys

from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store


def main():
    cat, ids = sys.argv[1], [x for x in sys.argv[2].split(",") if x]
    store = Store(DB_PATH)
    n = store.set_category_overrides({i: cat for i in ids})
    # 지금 랭킹에도 반영 — 같은 트랜잭션 계약(merge)으로 기존 항목에 덮는다.
    with store._conn() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT value FROM settings WHERE key='last_run::youtube'").fetchone()
        d = json.loads(row[0]) if row and row[0] else {"items": []}
        before = sum(1 for x in d["items"] if x.get("shortcode") in set(ids) and x.get("category") == cat)
        store._apply_overrides(d["items"], conn=c)
        c.execute("UPDATE settings SET value=? WHERE key='last_run::youtube'",
                  (json.dumps(d, ensure_ascii=False),))
        after = sum(1 for x in d["items"] if x.get("shortcode") in set(ids) and x.get("category") == cat)
    print(f"[override] 지정 {n}건 → {cat or '해제'} · 랭킹 반영 {before}→{after}")


if __name__ == "__main__":
    main()
