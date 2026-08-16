"""CN(샤오홍슈·도우인) 검색 단일 진입점.

호출부는 **어느 백엔드가 도는지 모른다.** Playwright(무료)를 먼저 시도하고
0건이면 Apify(유료)로 폴백한다.

★어느 백엔드를 쓸지는 아래 _CHAIN **한 곳에서만** 정한다(0순위-B: 같은 판단을
두 번 적으면 언젠가 어긋난다). 도우인 세션이 생기면 pw_douyin이 성공하기 시작해
자동으로 비용이 0이 된다 — 이 표도, 호출부도, 프론트도 고칠 필요가 없다.

비용(2026-08-17 실측): 도우인 Apify $0.04005/회 · 샤오홍슈 Apify $0.098/회.
Apify 무료한도는 계정당 월 $5이며 **이월되지 않는다**(안 쓰면 소멸) —
그래서 '0건이면 폴백'이 맞다. 돈 아끼려다 결과를 못 보는 쪽이 더 비싼 손해다.
"""
from concurrent.futures import ThreadPoolExecutor

from shopping_shorts import cn_backends

# 회당 비용(달러). meta에 실어 화면에 노출한다 — 비용이 조용히 새는 걸 막는다.
_COST = {"apify_douyin": 0.04005, "apify_xiaohongshu": 0.098}

_CHAIN = {
    "xiaohongshu": [cn_backends.pw_xiaohongshu, cn_backends.apify_xiaohongshu],
    "douyin": [cn_backends.pw_douyin, cn_backends.apify_douyin],
}


def _run_chain(chain, keyword, max_results):
    """사슬을 순서대로 시도. **0건이면 다음으로 넘어간다**(A안).

    백엔드는 계약상 예외를 안 던지지만, 그래도 여기서 한 번 더 막는다 —
    사슬이 백엔드 하나 때문에 통째로 죽으면 안 된다."""
    for fn in chain:
        try:
            rows = fn(keyword, max_results) or []
        except Exception:
            continue
        if rows:
            name = getattr(fn, "__name__", "unknown")
            return rows, {"backend": name, "n": len(rows),
                          "cost_usd": _COST.get(name, 0)}
    return [], {"backend": None, "n": 0, "cost_usd": 0}


def search(keyword, max_results=10):
    """키워드 → 샤오홍슈+도우인 결과(플랫폼 병렬).

    반환: {"items": [...], "count": N, "keyword": kw, "meta": {플랫폼: {...}}}
    items의 각 dict는 기존 렌즈 카드와 같은 스키마다(프론트 재사용)."""
    kw = (keyword or "").strip()
    if not kw:
        return {"items": [], "count": 0, "keyword": "", "meta": {}}
    n = max(1, min(int(max_results or 10), 60))

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {p: ex.submit(_run_chain, chain, kw, n)
                   for p, chain in _CHAIN.items()}
        results = {}
        for platform, f in futures.items():
            try:
                results[platform] = f.result()
            except Exception:
                # 한 플랫폼이 통째로 죽어도 다른 플랫폼은 살린다
                results[platform] = ([], {"backend": None, "n": 0, "cost_usd": 0})

    items, meta = [], {}
    for platform, (rows, m) in results.items():
        items.extend(rows)
        meta[platform] = m
    return {"items": items, "count": len(items), "keyword": kw, "meta": meta}
