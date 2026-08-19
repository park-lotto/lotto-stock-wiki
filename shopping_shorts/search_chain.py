"""키워드 검색 사슬 엔진 — 플랫폼과 무관한 뼈대(2026-08-17).

`cn_search`(샤오홍슈·도우인)가 쓰던 구조를 그대로 뽑아낸 것이다. 인스타·틱톡·
유튜브(`kw_search`)도 **똑같은 판단**을 해야 하는데, 그걸 두 번 적으면 언젠가
어긋난다(0순위-B). 그래서 "무료 먼저 → 0건이면 다음" 규칙은 여기 한 곳에만 있다.

계약:
  백엔드 fn(keyword, max_results) -> [정규화된 row, ...]
    · 예외를 던지지 않는다(던져도 여기서 막는다 — 사슬이 통째로 죽으면 안 된다)
    · 결과가 없으면 빈 리스트. **0건도 폴백 사유**다(예외뿐 아니라).
"""
from concurrent.futures import ThreadPoolExecutor


def run_chain(chain, keyword, max_results, cost_table=None):
    """사슬을 순서대로 시도하고 **처음으로 결과가 나온** 백엔드에서 멈춘다.

    반환: (rows, meta) — meta = {"backend": 이름, "n": 개수, "cost_usd": 회당비용}
    """
    costs = cost_table or {}
    for fn in chain:
        try:
            rows = fn(keyword, max_results) or []
        except Exception:
            continue
        if rows:
            name = getattr(fn, "__name__", "unknown")
            return rows, {"backend": name, "n": len(rows),
                          "cost_usd": costs.get(name, 0)}
    return [], {"backend": None, "n": 0, "cost_usd": 0}


def search_many(chains, keyword, max_results=10, cost_table=None, max_len=60):
    """플랫폼들을 **동시에** 돌려 합친다. 한 플랫폼이 죽어도 나머지는 살린다.

    반환: {"items": [...], "count": N, "keyword": kw, "meta": {플랫폼: {...}}}
    """
    kw = (keyword or "").strip()
    if not kw:
        return {"items": [], "count": 0, "keyword": "", "meta": {}}
    n = max(1, min(int(max_results or 10), max_len))

    with ThreadPoolExecutor(max_workers=max(1, len(chains))) as ex:
        futures = {p: ex.submit(run_chain, chain, kw, n, cost_table)
                   for p, chain in chains.items()}
        results = {}
        for platform, f in futures.items():
            try:
                results[platform] = f.result()
            except Exception:
                results[platform] = ([], {"backend": None, "n": 0, "cost_usd": 0})

    items, meta = [], {}
    for platform, (rows, m) in results.items():
        items.extend(rows)
        meta[platform] = m
    return {"items": items, "count": len(items), "keyword": kw, "meta": meta}
