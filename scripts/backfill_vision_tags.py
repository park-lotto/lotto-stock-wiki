"""기존 랭킹 아이템(last_run)에 썸네일 비전 주제태그를 채운다 — 검색 정확도 백필(2026-07-19).

수집 훅(_tag_new_items)은 새로 수집되는 것만 태깅하므로, 이미 쌓인 아이템은 이 스크립트로
한 번 돌려 채운다. shortcode 캐시 덕에 이미 태그 있는 건 건너뛴다(재실행 안전·무과금).

사용:  python -m scripts.backfill_vision_tags [--limit N] [--platform instagram]
서버(systemd에 SHORTS_GEMINI_KEY 있음)에서 실행. 로컬은 키 없어 스킵된다.
"""
import argparse
import sys
from collections import Counter

from shopping_shorts.config import DB_PATH, SHORTS_GEMINI_KEYS
from shopping_shorts.store import Store
from shopping_shorts import video_analysis
from shopping_shorts import vision_tagging


def backfill(limit=None, platform="instagram"):
    if not SHORTS_GEMINI_KEYS:
        print("SHORTS_GEMINI_KEY 없음 — 태깅 불가(서버에서 실행하세요).")
        return 0
    store = Store(DB_PATH)
    if platform == "instagram":
        items, collected_at = store.load_last_run()
    else:
        items, collected_at = store.load_last_run_platform(platform)
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

    # ★태깅만 하면 카테고리는 그대로다(2026-07-31). 비전태그는 원래 '검색'만 썼고
    # 분류기는 캡션을 보는데, 그 캡션이 429 회피(상세조회 off)로 100% 비어 있다.
    # → 태그를 채운 김에 그 태그로 카테고리를 다시 매기고 화면 캐시에 반영한다.
    #   (수집 경로도 같은 동작: daily_instagram_collect / app._run_collect_job)
    changed = vision_tagging.recategorize_by_vision(items, DB_PATH)
    changed += vision_tagging.apply_channel_category(items, DB_PATH)   # 태그 없는 것만 채널지정으로
    if changed:
        # collected_at은 그대로 둔다 — 새로 수집한 게 아니라 같은 수집분을 다시 분류한 것이라
        # '마지막 수집' 시각을 속이면 안 된다.
        if platform == "instagram":
            store.save_last_run(items, collected_at)
        else:
            store.save_last_run_platform(platform, items, collected_at)
    print(f"카테고리 재분류: {changed}건 변경 · 분포 {dict(Counter(i.get('category') for i in items).most_common())}")
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--platform", default="instagram")
    a = ap.parse_args()
    sys.exit(0 if backfill(a.limit, a.platform) >= 0 else 1)
