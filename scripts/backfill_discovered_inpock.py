# -*- coding: utf-8 -*-
"""발굴·등록 채널의 판매채널 링크 1회 채우기(2026-09-26).

  py scripts/backfill_discovered_inpock.py            # 링크 없는 채널 전부(채널당 프로필 1회)
  py scripts/backfill_discovered_inpock.py --limit 20 --dry

프로필을 열어 외부 링크(인포크 등)를 discovered_channels.inpock에 넣는다. 이미 있는 채널은 건너뛴다.
다음 수집부터 카드에 🛒판매채널이 붙는다(collect union 메타가 이 칸을 싣는다)."""
import argparse, sys, time
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts.service import enrich_discovered_profile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    st = Store(DB_PATH)
    todo = [c for c in st.discovered_channels() if not (c.get("inpock") or "").strip()]
    if a.limit:
        todo = todo[:a.limit]
    print(f"대상 {len(todo)}채널", file=sys.stderr)
    done = 0
    for c in todo:
        u = c["username"]
        if a.dry:
            print("dry", u); continue
        n = enrich_discovered_profile(u, store=st)
        done += 1 if n else 0
        print(f"{u}: {'링크 저장' if n else '링크 없음/실패'}")
        time.sleep(a.sleep)
    print(f"완료: {done}/{len(todo)} 저장", file=sys.stderr)


if __name__ == "__main__":
    main()
