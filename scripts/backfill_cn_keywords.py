"""저장된 소재 주제(vision_tags.subject)를 중국어 검색어로 미리 번역해 캐시한다 —
샤오홍슈·도우인 트렌드 검색카드 백필(2026-07-25).

트렌드 검색카드 엔드포인트(/api/reference/cn_trend)는 크롤·번역을 호출하지 않고 캐시만
읽는다(무과금·즉시). 그래서 소재가 새로 쌓일 때마다 이 배치를 돌려 cn_keyword_cache를
미리 채워둔다. 이미 캐시에 있는 소재는 건너뛴다(재실행 안전·무과금).

캐시 미스가 남으면 프론트가 그 카드의 중국 플랫폼 버튼을 흐리게 처리한다(폴백 B) —
이 배치를 돌리면 미스가 줄어 버튼이 살아난다.

사용:  python -m scripts.backfill_cn_keywords [--limit N]
서버(systemd에 SHORTS_GEMINI_KEY 있음)에서 실행. 로컬은 키 없어 스킵된다.
"""
import argparse
import sys

from shopping_shorts.config import DB_PATH, SHORTS_GEMINI_KEYS
from shopping_shorts.store import Store
from shopping_shorts.video_analysis import translate_keyword


def backfill(limit=None):
    if not SHORTS_GEMINI_KEYS:
        print("SHORTS_GEMINI_KEY 없음 — 번역 불가(서버에서 실행하세요).")
        return 0
    store = Store(DB_PATH)
    # 저장된 모든 소재 주제(중복 제거) 중 아직 중국어 캐시가 없는 것만.
    with store._conn() as c:
        subjects = [r[0].strip() for r in c.execute(
            "SELECT DISTINCT subject FROM vision_tags WHERE subject IS NOT NULL AND subject!=''"
        ).fetchall() if r[0] and r[0].strip()]
    cached = store.cn_keyword_map(subjects)   # 이미 zh 있는 것
    todo = [s for s in subjects if s not in cached]
    if limit:
        todo = todo[:limit]
    print(f"대상 {len(todo)}건 / 전체 소재 {len(subjects)}건 (이미 캐시 {len(cached)}건)")
    done = 0
    for i, subj in enumerate(todo, 1):
        zh = (translate_keyword(subj).get("zh") or "").strip()
        if zh:
            store.save_cn_keyword(subj, zh)
            done += 1
            print(f"  [{i}/{len(todo)}] {subj} → {zh}")
        else:
            print(f"  [{i}/{len(todo)}] {subj} 번역 비어 — 스킵(다음 실행에 재시도)")
    print(f"완료: {done}건 번역·캐시됨.")
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    sys.exit(0 if backfill(a.limit) >= 0 else 1)
