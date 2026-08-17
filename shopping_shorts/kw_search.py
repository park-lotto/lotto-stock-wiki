"""한국어 키워드 검색 단일 진입점 — 인스타·틱톡·유튜브(2026-08-17).

`cn_search`(샤오홍슈·도우인)의 형제이고, **사슬 엔진은 같은 것을 쓴다**
(`search_chain`). 즉 "무료 먼저 → 0건이면 다음" 규칙이 두 군데 적히지 않는다.

호출부는 어느 백엔드가 도는지 모른다. 나중에 틱톡 무료 경로(yt-dlp)가 생기면
아래 `_CHAIN`에 한 줄 끼우면 되고, 엔드포인트도 프론트도 안 고친다.

검색어가 CN과 다르다 — 여기는 **한국어(ko)**, cn_search는 중국어(zh)다.
같은 후보 행에서 버튼만 갈린다.
"""
from shopping_shorts import kw_backends, search_chain

# 회당 비용(달러). meta로 화면에 노출한다 — 비용이 조용히 새는 걸 막는다.
#   유튜브·인스타는 0원이다(유튜브=무료쿼터 / 인스타=우리 프록시. 프록시 바이트
#   요금은 렌즈가 아니라 프록시 예산에서 나가므로 여기 회당 비용은 0으로 둔다).
#
# 틱톡 = Apify `clockworks/tiktok-scraper` 유료.
# ★2026-08-17 서버 실측: 5건 요청 1회 = **$0.0195** (run usageTotalUsd 직접 확인).
#   개수에 따라 늘어나므로 기본 8건이면 대략 $0.03 언저리다 — 정확한 값이 필요하면
#   Apify 콘솔의 run usageTotalUsd를 다시 재라(여기 숫자를 짐작으로 고치지 마라).
#   참고: 샤오홍슈 $0.098 · 도우인 $0.04005보다는 싸다.
_COST = {"tiktok": 0.0195}

_CHAIN = {
    "instagram": [kw_backends.instagram],
    "tiktok": [kw_backends.tiktok],
    "youtube": [kw_backends.youtube],
}


def search(keyword, max_results=10):
    """한국어 키워드 → 인스타+틱톡+유튜브 결과(플랫폼 병렬).

    반환: {"items": [...], "count": N, "keyword": kw, "meta": {플랫폼: {...}}}
    items는 렌즈 카드와 같은 스키마다(cn_backends.normalize 공용)."""
    return search_chain.search_many(_CHAIN, keyword, max_results, _COST)
