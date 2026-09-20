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
    # 슬롯마다 같은 검색어를 쓰는 종전 동작 = 아래 일반형의 특수한 경우다(0순위-B:
    # 병렬·예외격리·meta 합치기를 두 벌로 적지 않는다).
    return search_many_kw({p: (chain, kw) for p, chain in chains.items()},
                          max_results, cost_table, max_len, keyword=kw)


def search_many_kw(slots, max_results=10, cost_table=None, max_len=60, keyword=""):
    """슬롯마다 **검색어가 다를 수 있는** 병렬 실행 (2026-09-08).

    slots: {슬롯키: (백엔드사슬, 그 슬롯에 넣을 검색어)}
      슬롯키는 "youtube" 처럼 플랫폼명이어도 되고, 다국어를 돌릴 때처럼
      "youtube@en" 이어도 된다 — meta의 키로만 쓰인다. 카드에 찍히는
      `platform`은 백엔드가 normalize에서 정하므로 슬롯키와 무관하다.

    왜 필요한가(사장님 지시 "중국어 영어 일본어까지 배치되게"): 소재 영상은
    한국어 검색만으로는 안 나온다. 핀터레스트가 이미 그 이유로 자체 번역을
    하고 있었는데(실측: '인덕션 테이블' 0건 / 'induction table' 12건), 그 판단이
    한 백엔드 안에 갇혀 있어 다른 플랫폼은 혜택을 못 봤다.
    """
    n = max(1, min(int(max_results or 10), max_len))
    live = {k: v for k, v in (slots or {}).items() if v and (v[1] or "").strip()}
    if not live:
        return {"items": [], "count": 0, "keyword": keyword or "", "meta": {}}

    with ThreadPoolExecutor(max_workers=max(1, len(live))) as ex:
        futures = {p: ex.submit(run_chain, chain, (kw_ or "").strip(), n, cost_table)
                   for p, (chain, kw_) in live.items()}
        results = {}
        for platform, f in futures.items():
            try:
                results[platform] = f.result()
            except Exception:
                results[platform] = ([], {"backend": None, "n": 0, "cost_usd": 0})

    items, meta = [], {}
    seen = set()
    for platform, (rows, m) in results.items():
        for r in rows:
            # 같은 영상이 여러 언어 슬롯에서 겹쳐 올 수 있다(예: 영어 제목 영상이
            # en·ja 양쪽에서). url로 한 번만 담는다 — 프론트도 중복을 거르지만
            # 여기서 걸러야 meta의 건수와 화면 건수가 어긋나지 않는다.
            u = r.get("url")
            if u and u in seen:
                continue
            if u:
                seen.add(u)
            items.append(r)
        meta[platform] = m
    return {"items": items, "count": len(items),
            "keyword": keyword or "", "meta": meta}
