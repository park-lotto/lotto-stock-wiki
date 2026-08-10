"""카테고리가 비어 있는 인스타 채널만 골라 릴스 1건의 캡션으로 카테고리를 채운다.

왜 필요한가(2026-07-30): 429를 잡으려고 릴스 상세 REST(캡션 포함)를 껐다. 그 뒤로
- 기존 채널은 과거 이력의 최빈 카테고리로 폴백하고(store.channel_categories)
- 신규 발굴 채널은 찾아낸 해시태그로 채운다(categorize.category_of_hashtag)
그런데 **그 전에 이미 등록됐지만 이력도 태그도 없는 채널**은 영영 '기타'로 남는다.
이 스크립트가 그 잔여분만 한 번 훑는다. 채널당 REST 1건이라 부담이 작다.

쓰는 법:
    python3 scripts/backfill_channel_category.py            # 실제 반영
    python3 scripts/backfill_channel_category.py --dry-run  # 뭘 채울지만 출력
    python3 scripts/backfill_channel_category.py --limit 30 # 한 번에 30채널만(429 회피)
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts import instagram_playwright                     # noqa: E402
from shopping_shorts.categorize import categorize                    # noqa: E402
from shopping_shorts.config import DB_PATH                           # noqa: E402
from shopping_shorts.instagram_parse import classify_channel_result  # noqa: E402
from shopping_shorts.store import Store                              # noqa: E402


def _targets(store, limit):
    """카테고리를 못 정한 발굴 채널 목록(이력 폴백으로도 안 채워지는 것만)."""
    known = store.channel_categories()          # 이력으로 이미 아는 채널
    out = []
    for ch in store.discovered_channels():
        u = (ch.get("username") or "").lower().lstrip("@")
        if not u or (ch.get("category") or "").strip() or u in known:
            continue
        out.append(ch)
        if limit and len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--sleep", type=float, default=2.0, help="채널 간 대기(초) — 429 회피")
    args = ap.parse_args()

    store = Store(DB_PATH)
    targets = _targets(store, args.limit)
    print(f"[backfill] 대상 {len(targets)}채널")
    filled = 0
    for ch in targets:
        uname = ch["username"]
        nodes, page_url, err = instagram_playwright._scrape_one_playwright(uname)
        if classify_channel_result(nodes, page_url, err) != "ok" or not nodes:
            print(f"  - {uname}: 스크레이프 실패(스킵)")
            time.sleep(args.sleep)
            continue
        # 캡션은 목록 응답에 없다 → 대표 릴스 1건만 상세 REST로 가져온다.
        caption = ""
        with instagram_playwright._detail_context() as ctx:
            for n in nodes[:1]:
                pk = n.get("pk")
                d = instagram_playwright._fetch_reel_detail(ctx, pk) if pk else None
                cap = (d or {}).get("caption")
                caption = cap.get("text", "") if isinstance(cap, dict) else (cap or "")
        cat = categorize(ch.get("name") or uname, caption)
        if cat == "기타":
            print(f"  - {uname}: 판정 실패(기타) — 그대로 둠")
        else:
            if not args.dry_run:
                store.add_discovered(uname, name=ch.get("name") or uname, category=cat)
            filled += 1
            print(f"  + {uname}: {cat}")
        time.sleep(args.sleep)
    print(f"[backfill] {filled}채널 채움{' (dry-run, 저장 안 함)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
