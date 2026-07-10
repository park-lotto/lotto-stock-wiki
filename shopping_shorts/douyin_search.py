"""Apify Douyin Search Scraper(zen-studio/douyin-search-scraper)로 키워드
검색 → 정규화된 후보 리스트. apify_client.py의 토큰 로테이션을 재사용
(2026-07-10, 5대 플랫폼 확장 요청으로 추가).

실측(2026-07-10): 먼저 조사했던 natanielsantos~douyin-scraper 액터는 흔한
영어 키워드("iphone")로도 0건이 나와 신뢰도가 낮다고 판단해 보류했음.
같은 개발자(zen-studio)의 샤오홍슈 액터가 실제로 잘 작동했던 것에 착안해
zen-studio~douyin-search-scraper로 재시도 — "iphone" 키워드로 실제 영상
3건(재생 URL·썸네일 포함) 확인됨."""
from shopping_shorts.apify_client import _run_with_rotation
from shopping_shorts.config import APIFY_TOKENS

_ACTOR = "zen-studio~douyin-search-scraper"


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드 → [{url, title, thumbnail}, ...]."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("douyin_search: APIFY_TOKEN이 설정되지 않았습니다")
    payload = {"keywords": [keyword], "maxResultsPerQuery": max_results, "sort": "general"}
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        url = item.get("url")
        if not url or item.get("type") != "video":
            continue
        out.append({
            "url": url,
            "title": item.get("itemTitle") or item.get("text", ""),
            "thumbnail": (item.get("videoMeta") or {}).get("cover", ""),
        })
    return out
