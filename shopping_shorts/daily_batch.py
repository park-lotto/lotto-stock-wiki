"""대본 위키 학습소재 통계 배치(2026-07-13) — 매일 새벽 크론으로 실행.

1) backfill_structures: 대본추출됐지만 구조분석 안 된 항목을 채운다.
2) recompute_element_stats: 카테고리별로 쌓인 구조 데이터에서 요소별 자유서술 값을
   모아 element_stats.cluster_element_values()로 통계를 재계산한다(기존 값 덮어씀).

둘 다 부가기능(실패해도 서비스 자체엔 영향 없음) — 예외는 항목 단위로 삼켜서
한 건 실패가 전체를 막지 않게 한다."""
from shopping_shorts import element_stats
from shopping_shorts.structure_analyze import analyze_structure
from shopping_shorts.script_generate import ELEM_KEYS
from shopping_shorts.store import Store


def backfill_structures(store, limit=100):
    """구조분석 안 된 대본추출 항목에 analyze_structure()를 돌려 채운다.
    성공적으로 백필한 건수를 반환한다(항목 단위로 예외를 삼키므로 실패 건은 제외)."""
    targets = store.extracts_missing_structure(limit=limit)
    n = 0
    for t in targets:
        try:
            structure = analyze_structure(t["full_text"])
            store.save_extract_structure(t["shortcode"], structure)
            n += 1
        except Exception as e:
            print(f"daily_batch backfill 실패 {t['shortcode']}: {e}")
            continue
    return n


def recompute_element_stats(store, only_category=None):
    """카테고리 × 요소 조합마다 클러스터링을 재계산해 저장. 실제로 카테고리가
    저장된(표본 충분·클러스터링 성공) 조합 수를 반환. only_category가 주어지면
    그 카테고리만 재계산(위키 저장 직후 즉시 학습용, 2026-07-14)."""
    saved = 0
    cats_to_do = [only_category] if only_category else store.distinct_extract_categories()
    for product_category in cats_to_do:
        for element in ELEM_KEYS:
            try:
                values = store.element_raw_values(product_category, element)
                cats = element_stats.cluster_element_values(element, values)
                if cats:
                    for c in cats:
                        c["sample_count"] = len(values)
                    store.save_element_category_stats(product_category, element, cats)
                    saved += 1
            except Exception as e:
                print(f"daily_batch stats 실패 {product_category}/{element}: {e}")
                continue
    return saved


def run(db_path):
    """크론 엔트리포인트 — 백필 후 통계 재계산."""
    store = Store(db_path)
    n1 = backfill_structures(store)
    n2 = recompute_element_stats(store)
    print(f"daily_batch: 구조분석 백필 {n1}건, 카테고리 통계 저장 {n2}건")


if __name__ == "__main__":
    from shopping_shorts.config import DB_PATH
    run(DB_PATH)
