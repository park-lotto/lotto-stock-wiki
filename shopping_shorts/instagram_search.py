"""Apify Instagram Reels Search(data-slayer/instagram-search-reels)로 자유
텍스트 키워드 검색 → 정규화된 후보 리스트. apify_client.py의 토큰 로테이션을
재사용(2026-07-10 전면 교체).

기존 apify~instagram-hashtag-scraper(해시태그 정확일치 전용)는 여러 단어를
합친 해시태그가 실제로 안 쓰이면 0건이 나오고, 쓰인다 해도 인스타 자체
검색보다 결과가 부정확했음(사용자 실측: "실수집 결과는 의미없다" — 인스타
링크를 직접 열었을 때(자체 검색)는 정확했는데 우리 자동수집은 아니었음).

data-slayer~instagram-search-reels는 자유 텍스트 쿼리로 실제 인기 릴스를
검색해 인스타 자체검색과 비슷한 정확도를 보임(실측 2026-07-10: "iphone"
12건, "marker" 12건, "Marvy Uchida" 12건, "puffy velvet marker" 6건 —
전부 실제 관련 영상. 너무 길고 구체적인 4단어 복합어("Marvy Uchida Puffy
Velvet Marker")만 0건이었는데, 이건 그 정확한 문구를 쓰는 콘텐츠 자체가
희소해서지 액터 문제가 아님). 참고로 공식 apify~instagram-search-scraper의
"인기 릴스 검색" 모드는 두 번 다 "blocked by Instagram"으로 실패해 배제."""
from shopping_shorts.apify_client import _run_with_rotation
from shopping_shorts.config import APIFY_TOKENS

_ACTOR = "data-slayer~instagram-search-reels"


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드(자유 텍스트) → [{url, title, thumbnail}, ...]."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("instagram_search: APIFY_TOKEN이 설정되지 않았습니다")
    payload = {"query": keyword, "maxPages": 1}
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        code = item.get("code")
        if not code or not item.get("is_video"):
            continue
        caption = (item.get("caption") or {}).get("text", "")
        out.append({
            "url": f"https://www.instagram.com/reel/{code}/",
            "title": caption,
            "thumbnail": item.get("thumbnail_url", ""),
        })
        if len(out) >= max_results:
            break
    return out
