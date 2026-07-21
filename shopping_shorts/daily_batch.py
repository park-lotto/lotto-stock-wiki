"""대본 위키 학습소재 통계 배치(2026-07-13) — 매일 새벽 크론으로 실행.

1) backfill_structures: 대본추출됐지만 구조분석 안 된 항목을 채운다.
2) recompute_element_stats: 카테고리별로 쌓인 구조 데이터에서 요소별 자유서술 값을
   모아 element_stats.cluster_element_values()로 통계를 재계산한다(기존 값 덮어씀).

둘 다 부가기능(실패해도 서비스 자체엔 영향 없음) — 예외는 항목 단위로 삼켜서
한 건 실패가 전체를 막지 않게 한다."""
import json
import sys
from datetime import datetime, timezone

from shopping_shorts import element_stats
from shopping_shorts import perf_score
from shopping_shorts.structure_analyze import analyze_structure
from shopping_shorts.script_generate import ELEM_KEYS
from shopping_shorts.store import Store


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


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


def ingest_crawl_winners(store, platforms=("youtube", "tiktok", "instagram"),
                         grades=("S",), ingest_fn=None, call=None):
    """자동크롤 결합(Phase1): 우승 랭킹 아이템 중 대본이 이미 추출된 것을 부품은행에
    자동 흡수. 조인키=shortcode. url 중복은 스킵. 부가기능이라 개별 실패는 삼킨다."""
    if ingest_fn is None:
        from shopping_shorts import pattern_bank
        ingest_fn = pattern_bank.ingest_script
    wiki_by_sc = {}
    for w in store.wiki_list():
        if w.get("full_text"):
            wiki_by_sc[w.get("shortcode")] = w
    n = 0
    for platform in platforms:
        try:
            items, collected_at = store.load_last_run_platform(platform)
        except Exception:
            continue
        for it in items:
            try:
                if it.get("grade") not in grades:
                    continue
                w = wiki_by_sc.get(it.get("shortcode"))
                if not w:
                    continue
                url = it.get("url") or it.get("video_url") or ""
                if store.pattern_source_url_exists(url):
                    continue
                cs = w.get("category_source")
                category_source = cs if cs in ("user", "gemini") else None
                item = dict(it)
                item["collected_at"] = collected_at
                perf = perf_score.perf_from_item(item)
                ingest_fn(store, w["full_text"], source="crawl", url=url,
                          product_category=w.get("category"), category_source=category_source,
                          perf=perf, call=call)
                n += 1
            except Exception as e:      # 개별 실패는 배치 전체를 막지 않는다
                print(f"ingest_crawl_winners: {e!r}", file=sys.stderr)
    return n


def recompute_perf_scores(store, now_iso=None):
    """R4-clean 소스로 플랫폼별 peer 분포를 만들고, 각 부품 perf_score =
    그 부품을 인용한 소스들의 perf_score 최댓값. 개별 실패는 삼킨다."""
    if now_iso is None:
        now_iso = _now_iso()
    sources = store.list_pattern_sources(category_source=("user", "gemini"))
    peers_by_platform = {}
    for src in sources:
        p = src.get("perf")
        if p and p.get("platform"):
            peers_by_platform.setdefault(p["platform"], []).append(p)
    src_score = {}
    for src in sources:
        p = src.get("perf")
        src_score[src["id"]] = perf_score.compute_perf_score(p, peers_by_platform, now_iso) if p else 0.0
    n = 0
    for item in store.list_pattern_items(limit=100000):
        try:
            ids = item.get("source_ids") or json.loads(item.get("source_ids_json") or "[]")
            best = max((src_score.get(i, 0.0) for i in ids), default=0.0)
            store.set_pattern_item_perf(item["id"], best)
            n += 1
        except Exception as e:
            print(f"recompute_perf_scores: {e!r}", file=sys.stderr)
    return n


def cluster_and_gate_spines(store, call=None, now_iso=None):
    """클러스터 결과를 spine 테이블에 반영. 신규는 pending으로만 생성(자동승인 금지).
    source_count/perf_score 재집계. 승격(approved)은 사람 몫(게이트 source_count>=3 AND approved)."""
    if now_iso is None:
        now_iso = _now_iso()
    from shopping_shorts import spine_cluster
    sources = store.list_pattern_sources(category_source=("user", "gemini"))
    existing = store.list_spines()
    by_name = {e.get("name"): e for e in existing}
    assignments = spine_cluster.cluster_sources(sources, existing, call=call)
    assigned = new_spines = 0
    for a in assignments:
        try:
            name = a["spine_name"]
            if name == spine_cluster.NEW_SENTINEL:
                name = a.get("situation_type") or "무제 스파인"
            sp = by_name.get(name)
            if sp is None:
                sid = store.add_spine(name, situation_type=a.get("situation_type"), status="pending")
                sp = {"id": sid, "name": name}
                by_name[name] = sp
                new_spines += 1
            store.set_pattern_source_spine(a["source_id"], sp["id"])
            assigned += 1
        except Exception as e:
            print(f"cluster_and_gate_spines(assign): {e!r}", file=sys.stderr)
    # 재집계: 각 스파인의 소속 소스 수 + perf 평균
    peers = {}
    for src in sources:
        p = src.get("perf")
        if p and p.get("platform"):
            peers.setdefault(p["platform"], []).append(p)
    members = {}
    for src in store.list_pattern_sources(category_source=("user", "gemini")):
        if src.get("spine_id"):
            members.setdefault(src["spine_id"], []).append(src)
    for spine_id, srcs in members.items():
        try:
            scores = [perf_score.compute_perf_score(x["perf"], peers, now_iso)
                      for x in srcs if x.get("perf")]
            avg = sum(scores) / len(scores) if scores else 0.0
            store.update_spine_stats(spine_id, source_count=len(srcs), perf_score=avg)
        except Exception as e:
            print(f"cluster_and_gate_spines(stats): {e!r}", file=sys.stderr)
    return {"assigned": assigned, "new_spines": new_spines}


def harvest_hooks(store):
    """훅 자동수확(P2): 우승작 캡션에서 훅 후보를 hook 버킷 pending으로. 실패는 삼킨다."""
    try:
        from shopping_shorts import hook_harvest
        return hook_harvest.harvest_hooks_from_crawl(store)
    except Exception as e:
        print(f"daily_batch harvest_hooks: {e!r}", file=sys.stderr)
        return 0


def run(db_path):
    """크론 엔트리포인트 — 백필→통계→자동흡수→훅수확→perf재계산→스파인클러스터."""
    store = Store(db_path)
    n1 = backfill_structures(store)
    n2 = recompute_element_stats(store)
    n3 = ingest_crawl_winners(store)
    n6 = harvest_hooks(store)
    n4 = recompute_perf_scores(store)
    n5 = cluster_and_gate_spines(store)
    print(f"daily_batch: 구조 {n1} · 통계 {n2} · 자동흡수 {n3} · 훅수확 {n6} · perf {n4} · 스파인 {n5}")


if __name__ == "__main__":
    from shopping_shorts.config import DB_PATH
    run(DB_PATH)
