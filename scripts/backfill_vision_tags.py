"""기존 랭킹 아이템(last_run)에 썸네일 비전 주제태그를 채운다 — 검색 정확도 백필(2026-07-19).

수집 훅(_tag_new_items)은 새로 수집되는 것만 태깅하므로, 이미 쌓인 아이템은 이 스크립트로
한 번 돌려 채운다. shortcode 캐시 덕에 이미 태그 있는 건 건너뛴다(재실행 안전·무과금).

사용:  python -m scripts.backfill_vision_tags [--limit N] [--platform instagram]
서버(systemd에 SHORTS_GEMINI_KEY 있음)에서 실행. 로컬은 키 없어 스킵된다.
"""
import argparse
import sys

from shopping_shorts.config import DB_PATH, SHORTS_GEMINI_KEYS
from shopping_shorts.store import Store
from shopping_shorts import video_analysis


def backfill(limit=None, platform="instagram"):
    if not SHORTS_GEMINI_KEYS:
        print("SHORTS_GEMINI_KEY 없음 — 태깅 불가(서버에서 실행하세요).")
        return 0
    store = Store(DB_PATH)
    if platform == "instagram":
        items, _ = store.load_last_run()
    else:
        items, _ = store.load_last_run_platform(platform)
    have = store.vision_tags_map([it.get("shortcode") for it in items])
    todo = [it for it in items if it.get("shortcode") and it.get("shortcode") not in have
            and it.get("thumbnail")]
    if limit:
        todo = todo[:limit]
    print(f"대상 {len(todo)}건 / 전체 {len(items)}건 (이미 태그 {len(have)}건)")
    done = 0
    for i, it in enumerate(todo, 1):
        img = video_analysis.fetch_thumb_bytes(it.get("thumbnail"))
        if not img:
            print(f"  [{i}/{len(todo)}] {it['shortcode'][-14:]} 썸네일 실패 — 스킵")
            continue
        tags = video_analysis.subject_tags_vision(img, it.get("caption", ""))
        if tags and (tags.get("subject") or tags.get("keywords")):
            store.save_vision_tags(it["shortcode"], tags.get("subject", ""), tags.get("keywords", []))
            done += 1
            print(f"  [{i}/{len(todo)}] {it['shortcode'][-14:]} → {tags.get('subject','')} {tags.get('keywords',[])}")
        else:
            print(f"  [{i}/{len(todo)}] {it['shortcode'][-14:]} 태그 비어 — 스킵")
    print(f"완료: {done}건 태깅됨.")
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--platform", default="instagram")
    a = ap.parse_args()
    sys.exit(0 if backfill(a.limit, a.platform) >= 0 else 1)
