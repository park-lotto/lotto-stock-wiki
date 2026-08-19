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
from shopping_shorts import cn_backends, search_chain

# 회당 비용(달러). meta에 실어 화면에 노출한다 — 비용이 조용히 새는 걸 막는다.
_COST = {"apify_douyin": 0.04005, "apify_xiaohongshu": 0.098}

_CHAIN = {
    "xiaohongshu": [cn_backends.pw_xiaohongshu, cn_backends.apify_xiaohongshu],
    "douyin": [cn_backends.pw_douyin, cn_backends.apify_douyin],
}


def _run_chain(chain, keyword, max_results):
    """(호환용) 사슬 실행 — 실제 판단은 search_chain.run_chain 한 곳에 있다.

    2026-08-17: 인스타·틱톡·유튜브(kw_search)가 같은 규칙을 필요로 해서 엔진을
    `search_chain`으로 뽑았다. 이 이름은 기존 호출·테스트를 위해 남겨둔 얇은 껍데기다."""
    return search_chain.run_chain(chain, keyword, max_results, _COST)


def search(keyword, max_results=10):
    """중국어 키워드 → 샤오홍슈+도우인 결과(플랫폼 병렬).

    반환: {"items": [...], "count": N, "keyword": kw, "meta": {플랫폼: {...}}}
    items의 각 dict는 기존 렌즈 카드와 같은 스키마다(프론트 재사용)."""
    return search_chain.search_many(_CHAIN, keyword, max_results, _COST)
